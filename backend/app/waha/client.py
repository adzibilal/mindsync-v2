"""WAHA (WhatsApp HTTP API) client for sending messages."""

import base64

import httpx

from app.core.config import get_settings


class WahaClient:
    def __init__(self):
        self.settings = get_settings()
        self.base = self.settings.waha_url.rstrip("/")
        self.headers = {"X-Api-Key": self.settings.waha_api_key}

    async def _post(self, path: str, json: dict) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base}/api{path}",
                json=json,
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def _put(self, path: str, json: dict) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"{self.base}/api{path}",
                json=json,
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def send_seen(self, session: str, chat_id: str) -> None:
        """Mark message as seen (blue ticks)."""
        try:
            await self._post("/sendSeen", {"session": session, "chatId": chat_id})
        except httpx.HTTPError:
            pass  # non-critical

    async def start_typing(self, session: str, chat_id: str) -> None:
        """Show typing indicator."""
        try:
            await self._post("/startTyping", {"session": session, "chatId": chat_id})
        except httpx.HTTPError:
            pass

    async def stop_typing(self, session: str, chat_id: str) -> None:
        """Stop typing indicator."""
        try:
            await self._post("/stopTyping", {"session": session, "chatId": chat_id})
        except httpx.HTTPError:
            pass

    async def send_text(self, session: str, chat_id: str, text: str) -> dict:
        """Send a text message."""
        return await self._post(
            "/sendText",
            {"session": session, "chatId": chat_id, "text": text},
        )

    async def get_session_status(self, session: str) -> dict:
        """Get WAHA session status."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base}/api/sessions/{session}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_session_qr(self, session: str) -> str | None:
        """Get QR as a data URI (PNG) for direct <img src> rendering. None if no QR."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base}/api/{session}/auth/qr",
                params={"format": "image"},
                headers=self.headers,
            )
            if resp.status_code == 200:
                b64 = base64.b64encode(resp.content).decode()
                return f"data:image/png;base64,{b64}"
            return None

    def _session_config(self) -> dict:
        """Webhook config registered on the WAHA session (points back to this backend)."""
        return {
            "webhooks": [
                {
                    "url": f"{self.settings.webhook_url.rstrip('/')}/webhooks/waha",
                    "events": ["message"],
                    "hmac": {"key": self.settings.waha_hmac_key},
                }
            ]
        }

    async def start_session(self, session_name: str = "default") -> dict:
        """Create+start a WAHA session, registering the webhook back to this backend.

        If the session already exists, update its config then start it.
        """
        config = self._session_config()
        try:
            return await self._post(
                "/sessions",
                {"name": session_name, "start": True, "config": config},
            )
        except httpx.HTTPStatusError as e:
            # ponytail: session already exists — update config then start.
            if e.response.status_code in (409, 422):
                await self._put(f"/sessions/{session_name}", {"config": config})
                return await self._post(f"/sessions/{session_name}/start", {})
            raise

    async def stop_session(self, session_name: str = "default") -> dict:
        """Stop a WAHA session (keeps auth + config)."""
        return await self._post(f"/sessions/{session_name}/stop", {})

    async def restart_session(self, session_name: str = "default") -> dict:
        """Restart a WAHA session (keeps auth + config)."""
        return await self._post(f"/sessions/{session_name}/restart", {})

    async def logout_session(self, session_name: str = "default") -> dict:
        """Log out a WAHA session — disconnects the device, keeps config (re-scan needed)."""
        return await self._post(f"/sessions/{session_name}/logout", {})
