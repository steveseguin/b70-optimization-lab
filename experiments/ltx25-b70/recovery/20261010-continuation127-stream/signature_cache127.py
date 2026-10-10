"""Packet 127: memoize only the pure digest of freshly enumerated sampler keys.

Every call still enumerates live route/thread/key registrations. A hit requires
identical key objects retained by this bounded cache; on admission each object
was recursively proven to contain only exact immutable builtin tuples and
primitive leaves. Equality, hash equality and an object id alone never qualify
a hit. New, replaced, reordered or unsupported keys run the parent's complete
digest. Nothing here caches a safety state, tensor fact, fault or memory value.
"""
from collections import OrderedDict
import threading
import os


def launch(env=None):
    value = (os.environ if env is None else env).get(
        "LTX_SNAPSHOT_DIGEST_CACHE", "0")
    if type(value) is not str or value not in ("0", "1"):
        raise ValueError("LTX_SNAPSHOT_DIGEST_CACHE must be 0 or 1")
    return int(value)


_ATOMS = (str, bytes, int, bool, type(None))


def deeply_immutable(value):
    """Conservative proof for actual describe()/describe_infrastructure() keys.

    Exact types exclude user-defined equality/repr and tuple subclasses. Floats
    and every other type deliberately use the parent, even if often immutable.
    The bounded walk avoids pathological nesting/size; refusal only means no
    caching, never skipping the parent check.
    """
    pending = [value]
    visited = 0
    while pending:
        item = pending.pop()
        visited += 1
        if visited > 100000:
            return False
        kind = type(item)
        if kind is tuple:
            pending.extend(item)
        elif kind not in _ATOMS:
            return False
    return True


class SignatureDigestCache:
    def __init__(self, max_entries=48):
        if type(max_entries) is not int or not 1 <= max_entries <= 48:
            raise ValueError('Signature digest cache needs 1..48 entries')
        self.max_entries = max_entries
        self.entries = OrderedDict()
        self.lock = threading.Lock()
        self.hits = self.misses = self.fallbacks = 0

    def digest(self, keys, original):
        # Copy the just-enumerated roots. Strong references prevent id reuse.
        roots = tuple(keys)
        identity = (id(original), tuple(id(key) for key in roots))
        with self.lock:
            held = self.entries.get(identity)
            if held is not None and held[2] is original and len(held[0]) == len(roots) and all(
                    old is new for old, new in zip(held[0], roots)):
                self.entries.move_to_end(identity)
                self.hits += 1
                return held[1]
            self.misses += 1
            value = original(roots)
            if not all(deeply_immutable(key) for key in roots):
                self.fallbacks += 1
                return value
            self.entries[identity] = (roots, value, original)
            self.entries.move_to_end(identity)
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)
            return value

    def summary(self):
        with self.lock:
            return {'entries': len(self.entries), 'max_entries': self.max_entries,
                    'hits': self.hits, 'misses': self.misses, 'fallbacks': self.fallbacks,
                    'rule': 'fresh roots; identical deeply immutable objects; parent digest on every miss'}
