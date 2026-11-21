import threading
import time
from collections import OrderedDict
from typing import Any, Callable

MISSING = object()


class TTLCache:
    """Small thread-safe in-memory cache with per-entry TTL and a size cap (oldest evicted).

    Deliberately behind a tiny interface (get/set) so Redis can replace it later.
    """

    def __init__(self, max_size: int = 1000, clock: Callable[[], float] = time.monotonic):
        self._max_size = max_size
        self._clock = clock
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any:
        """Returns the cached value or the MISSING sentinel (None is a valid cached value)."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return MISSING
            expires_at, value = entry
            if self._clock() >= expires_at:
                del self._data[key]
                return MISSING
            return value

    def set(self, key: Any, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._data[key] = (self._clock() + ttl_seconds, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
