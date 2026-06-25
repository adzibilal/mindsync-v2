"""Rate limiter — per-chatId sliding window rate limiting."""

import time
from collections import defaultdict


class RateLimiter:
    """
    Sliding window rate limiter per chat_id.
    Allows max_requests within window_seconds.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, chat_id: str) -> bool:
        """Check if a request from chat_id is allowed."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Remove old timestamps
        self._requests[chat_id] = [
            ts for ts in self._requests[chat_id] if ts > cutoff
        ]

        if len(self._requests[chat_id]) >= self.max_requests:
            return False

        self._requests[chat_id].append(now)
        return True

    def remaining(self, chat_id: str) -> int:
        """Get remaining requests for a chat_id."""
        now = time.time()
        cutoff = now - self.window_seconds
        self._requests[chat_id] = [
            ts for ts in self._requests[chat_id] if ts > cutoff
        ]
        return max(0, self.max_requests - len(self._requests[chat_id]))

    def reset(self, chat_id: str) -> None:
        """Reset rate limit for a chat_id."""
        self._requests.pop(chat_id, None)


# Global instance
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
