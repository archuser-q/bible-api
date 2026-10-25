"""Bảo vệ các API tốn tiền/tài nguyên: bắt buộc API key + giới hạn số request."""

import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Depends(api_key_header)):
    expected = os.getenv("APP_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Server chưa cấu hình APP_API_KEY")
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="API key không hợp lệ")

WINDOW_SECONDS = 60
_history: dict[str, deque] = defaultdict(deque)  
_lock = threading.Lock()  


def rate_limit(request: Request):
    limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()

    with _lock:
        timestamps = _history[client]
        # Bỏ các request đã quá 60 giây
        while timestamps and now - timestamps[0] > WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= limit:
            retry_after = int(WINDOW_SECONDS - (now - timestamps[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Quá {limit} request/phút, thử lại sau {retry_after} giây",
                headers={"Retry-After": str(retry_after)},
            )
        timestamps.append(now)
