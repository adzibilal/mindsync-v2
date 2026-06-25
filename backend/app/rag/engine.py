"""RAG engine — embeddings (via API), retrieval, and generation."""

import asyncio
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RagEngine:
    """Orchestrates the RAG pipeline: embed → retrieve → generate."""

    def __init__(self):
        self.settings = get_settings()
        self._qdrant = None

    @property
    def qdrant(self):
        if self._qdrant is None:
            from qdrant_client import QdrantClient
            self._qdrant = QdrantClient(url=self.settings.qdrant_url)
        return self._qdrant

    async def _api_embed(self, text: str) -> list[float]:
        """Embed text via router API endpoint."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.settings.embedding_api_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.settings.embedding_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.embedding_model,
                    "input": text,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    async def _api_embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts via API — one at a time to keep it simple."""
        results = []
        for t in texts:
            emb = await self._api_embed(t)
            results.append(emb)
        return results

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        return await self._api_embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return await self._api_embed_batch(texts)

    def ensure_collection(self, collection_name: str = "knowledge_base") -> None:
        """Create Qdrant collection if it doesn't exist (sync, called during startup)."""
        collections = self.qdrant.get_collections().collections
        if not any(c.name == collection_name for c in collections):
            dim = self.settings.embedding_dim
            self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config={"size": dim, "distance": "Cosine"},
            )
            logger.info(f"Created Qdrant collection '{collection_name}' (dim={dim})")

    async def upsert_chunks(
        self,
        chunks: list[str],
        metadatas: list[dict],
        collection_name: str = "knowledge_base",
    ) -> None:
        """Embed and upsert chunks to Qdrant."""
        self.ensure_collection(collection_name)
        embeddings = await self.embed_batch(chunks)

        points = []
        for i, (chunk, embedding, meta) in enumerate(zip(chunks, embeddings, metadatas)):
            # Use UUID5 for deterministic, valid point IDs
            import uuid
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{meta.get('document_id', '')}_{meta.get('chunk_index', i)}"))
            points.append({
                "id": point_id,
                "vector": embedding,
                "payload": {"text": chunk, **meta},
            })

        self.qdrant.upsert(collection_name=collection_name, points=points)
        logger.info(f"Upserted {len(points)} chunks to Qdrant")

    async def search(
        self, query: str, top_k: int | None = None, threshold: float | None = None,
        collection_name: str = "knowledge_base",
    ) -> list[dict]:
        """Search for relevant chunks given a query."""
        if top_k is None:
            top_k = self.settings.default_top_k
        if threshold is None:
            threshold = self.settings.default_threshold

        query_vector = await self.embed_text(query)

        # Use query_points (qdrant-client v1.18+ API)
        response = self.qdrant.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            score_threshold=threshold,
        )

        hits = response.points

        results = []
        for hit in hits:
            results.append({
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "source": hit.payload.get("source", ""),
                "document_id": hit.payload.get("document_id", ""),
                "chunk_index": hit.payload.get("chunk_index", 0),
            })
        return results

    async def generate_answer(
        self,
        query: str,
        context: str,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Generate answer via LLM through router with retry logic."""
        if system_prompt is None:
            system_prompt = self.settings.default_system_prompt

        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for h in history[-self.settings.default_max_history_turns * 2:]:
                messages.append(h)

        if context.strip():
            messages.append({
                "role": "system",
                "content": f"Gunakan konteks berikut untuk menjawab:\n\n{context}",
            })
        else:
            messages.append({
                "role": "system",
                "content": "Tidak ada konteks yang relevan. Katakan bahwa kamu tidak memiliki informasi tersebut.",
            })

        messages.append({"role": "user", "content": query})

        max_retries = self.settings.llm_max_retries
        base_delay = self.settings.llm_retry_base_delay
        timeout = self.settings.llm_timeout
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(
                        f"{self.settings.litellm_base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.settings.litellm_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.settings.litellm_model,
                            "messages": messages,
                            "temperature": 0.3,
                            "max_tokens": 1024,
                            "stream": False,
                        },
                    )

                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("retry-after", base_delay * (2 ** attempt)))
                        logger.warning(
                            f"LLM rate limited (429), retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    resp.raise_for_status()
                    data = resp.json()
                    answer = data["choices"][0]["message"]["content"]

                    if attempt > 0:
                        logger.info(f"LLM call succeeded on attempt {attempt + 1}")

                    return answer

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                last_error = e
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        logger.error(f"LLM call failed after {max_retries} attempts: {last_error}")
        raise last_error or Exception("LLM call failed after all retries")

    async def generate_answer_stream(
        self,
        query: str,
        context: str,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
    ):
        """Generate answer via LLM with streaming. Yields text chunks."""
        if system_prompt is None:
            system_prompt = self.settings.default_system_prompt

        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for h in history[-self.settings.default_max_history_turns * 2:]:
                messages.append(h)

        if context.strip():
            messages.append({
                "role": "system",
                "content": f"Gunakan konteks berikut untuk menjawab:\n\n{context}",
            })
        else:
            messages.append({
                "role": "system",
                "content": "Tidak ada konteks yang relevan. Katakan bahwa kamu tidak memiliki informasi tersebut.",
            })

        messages.append({"role": "user", "content": query})

        timeout = self.settings.llm_timeout

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.settings.litellm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.litellm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.litellm_model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def answer_query(
        self,
        query: str,
        history: list[dict] | None = None,
        include_sources: bool = False,
    ) -> dict:
        """Full RAG pipeline: retrieve + generate."""
        try:
            results = await self.search(query)

            context = "\n\n".join(
                f"[Source: {r['source'] or 'unknown'}] {r['text']}"
                for r in results
            )

            if not results:
                answer = await self.generate_answer(query, "", history)
                return {"answer": answer, "sources": []}

            answer = await self.generate_answer(query, context, history)

            result = {"answer": answer, "sources": results if include_sources else []}
            return result

        except Exception as e:
            logger.error(
                "rag_pipeline_error",
                extra={"error": str(e), "query": query[:100]},
                exc_info=True,
            )
            return {
                "answer": self.settings.llm_fallback_message,
                "sources": [],
            }
