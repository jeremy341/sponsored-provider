from collections import defaultdict, deque
from time import monotonic


class RateLimiter:
    def __init__(self):
        self.events = defaultdict(deque)

    def allow(self, key_id: int, limit: int, window_seconds: int = 60) -> bool:
        if limit <= 0:
            return True
        now = monotonic()
        events = self.events[key_id]
        while events and now - events[0] >= window_seconds:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True

