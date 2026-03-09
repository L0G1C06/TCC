import hashlib
import json


def make_cache_key(dataset, params):

    payload = json.dumps(
        {"dataset": dataset, "params": params},
        sort_keys=True
    )

    return hashlib.md5(payload.encode()).hexdigest()