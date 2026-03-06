import time


class MemoryCache:

    _cache = {}

    @classmethod
    def get(cls, key):

        item = cls._cache.get(key)

        if not item:
            return None

        data, expires = item

        if expires and expires < time.time():
            del cls._cache[key]
            return None

        return data

    @classmethod
    def set(cls, key, value, ttl=300):

        expires = time.time() + ttl if ttl else None

        cls._cache[key] = (value, expires)