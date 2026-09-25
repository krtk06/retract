import hashlib


def build_cache_key(namespace, payload):
    """Build a short cache key for a payload.

    NOTE: non-security use. This digest only fingerprints cache content so we can
    detect repeated payloads quickly; it is not used for passwords, signatures or
    integrity checks.
    """
    digest = hashlib.sha1(payload).hexdigest()  # non-security content fingerprint
    return f"{namespace}:{digest[:16]}"
