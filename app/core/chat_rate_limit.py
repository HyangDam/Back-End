from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import HTTPException, status


class ChatRateLimiter:
    """Small in-memory guard for the paid chat endpoint.

    Railway serverless instances can restart, so this is not a distributed
    limiter. It is intentionally a first safety layer for the MVP.
    """

    def __init__(self, per_minute: int = 5, per_day: int = 30):
        self.per_minute = per_minute
        self.per_day = per_day
        self._requests: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, client_key: str) -> None:
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)
        day_ago = now - timedelta(days=1)

        with self._lock:
            requests = self._requests[client_key]

            while requests and requests[0] < day_ago:
                requests.popleft()

            requests_in_last_minute = sum(
                request_time >= minute_ago for request_time in requests
            )

            if requests_in_last_minute >= self.per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Chat recommendation limit reached. Please try again in a minute.",
                )

            if len(requests) >= self.per_day:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily chat recommendation limit reached. Please try again tomorrow.",
                )

            requests.append(now)
