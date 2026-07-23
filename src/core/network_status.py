"""Simple network reachability check with short TTL cache."""



from __future__ import annotations



import socket

import time



_cache_until = 0.0

_cache_value = True





def is_online(timeout: float = 2.0, *, use_cache: bool = True) -> bool:

    """Return whether the network appears reachable.



    Cached for ~30s when ``use_cache`` is True to avoid blocking the UI thread.

    """

    global _cache_until, _cache_value

    now = time.monotonic()

    if use_cache and now < _cache_until:

        return _cache_value

    try:

        with socket.create_connection(("1.1.1.1", 53), timeout=timeout):

            value = True

    except OSError:

        value = False

    _cache_value = value

    _cache_until = now + 30.0

    return value





def invalidate_cache() -> None:

    global _cache_until

    _cache_until = 0.0

