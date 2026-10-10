"""CPU proof: immutable-key digest reuse never replaces live fact/state checks."""
import hashlib
import unittest
from signature_cache127 import SignatureDigestCache, deeply_immutable, launch


def original(keys):
    return hashlib.sha256('\n'.join(sorted(repr(k) for k in keys)).encode()).hexdigest()


class SignatureCacheTests(unittest.TestCase):
    def test_exact_digest_and_repeated_hit(self):
        keys = [('T', (1, 304, 4096), 'torch.bfloat16', 'xpu:0', (1245184, 4096, 1), True, False),
                ('S', 'None')]
        cache = SignatureDigestCache()
        self.assertEqual(cache.digest(keys, original), original(keys))
        self.assertEqual(cache.digest(list(keys), original), original(keys))
        self.assertEqual(cache.summary()['hits'], 1)

    def test_key_replacement_recomputes(self):
        cache = SignatureDigestCache()
        keys = [tuple(['shape', 145])]
        cache.digest(keys, original)
        keys[0] = tuple(['shape', 169])
        self.assertEqual(cache.digest(keys, original), original(keys))
        self.assertEqual(cache.summary()['hits'], 0)

    def test_equal_distinct_key_recomputes(self):
        cache = SignatureDigestCache()
        first, second = tuple(['shape', 145]), tuple(['shape', 145])
        self.assertIsNot(first, second)
        cache.digest([first], original)
        cache.digest([second], original)
        self.assertEqual(cache.summary()['misses'], 2)

    def test_key_order_change_recomputes_exact_parent(self):
        cache = SignatureDigestCache()
        a, b = ('a',), ('b',)
        self.assertEqual(cache.digest([a, b], original), cache.digest([b, a], original))
        self.assertEqual(cache.summary()['misses'], 2)

    def test_key_count_change(self):
        cache = SignatureDigestCache()
        a, b = ('a',), ('b',)
        cache.digest([a], original)
        self.assertEqual(cache.digest([a, b], original), original([a, b]))
        self.assertEqual(cache.summary()['hits'], 0)

    def test_custom_mutable_hashable_leaf_never_cached(self):
        class Leaf:
            value = 1
            def __repr__(self):
                return str(self.value)
        leaf = Leaf()
        keys, cache = [(leaf,)], SignatureDigestCache()
        first = cache.digest(keys, original)
        leaf.value = 2
        second = cache.digest(keys, original)
        self.assertNotEqual(first, second)
        self.assertEqual(second, original(keys))
        self.assertEqual(cache.summary()['fallbacks'], 2)

    def test_subclasses_refused(self):
        class Tuple(tuple): pass
        class Int(int): pass
        class Str(str): pass
        for value in (Tuple((1,)), (Int(1),), (Str('a'),)):
            self.assertFalse(deeply_immutable(value))

    def test_mutable_containers_refused(self):
        for value in ([1], {'a': 1}, {1}, bytearray(b'a'), (([1],),)):
            self.assertFalse(deeply_immutable(value))

    def test_float_refused(self):
        for value in (1.0, -0.0, float('nan'), float('inf')):
            self.assertFalse(deeply_immutable((value,)))

    def test_all_supported_exact_atoms(self):
        self.assertTrue(deeply_immutable((None, True, False, 0, -1, 'a', b'a', ((),))))

    def test_bounded_cache_eviction(self):
        cache = SignatureDigestCache(max_entries=2)
        keys = [tuple(['a', i]) for i in range(3)]
        for key in keys:
            cache.digest([key], original)
        self.assertEqual(cache.summary()['entries'], 2)
        cache.digest([keys[0]], original)
        self.assertEqual(cache.summary()['misses'], 4)

    def test_invalid_capacity(self):
        for value in (0, 49, True, 1.0):
            with self.assertRaises(ValueError):
                SignatureDigestCache(value)

    def test_parent_error_propagates_no_entry(self):
        cache = SignatureDigestCache()
        def fail(keys): raise RuntimeError('parent failure')
        with self.assertRaisesRegex(RuntimeError, 'parent failure'):
            cache.digest([('a',)], fail)
        self.assertEqual(cache.summary()['entries'], 0)

    def test_empty_keys_exact(self):
        cache = SignatureDigestCache()
        self.assertEqual(cache.digest([], original), original([]))
        self.assertEqual(cache.digest([], original), original([]))
        self.assertEqual(cache.summary()['hits'], 1)

    def test_same_roots_changed_outer_container_hit(self):
        cache = SignatureDigestCache()
        a = tuple(['a', 1])
        cache.digest([a], original)
        self.assertEqual(cache.digest(iter([a]), original), original([a]))
        self.assertEqual(cache.summary()['hits'], 1)

    def test_launch_modes(self):
        self.assertEqual(launch({}), 0)
        self.assertEqual(launch({"LTX_SNAPSHOT_DIGEST_CACHE": "1"}), 1)
        for value in ("", "true", "2", 1, None):
            with self.assertRaises(ValueError):
                launch({"LTX_SNAPSHOT_DIGEST_CACHE": value})

    def test_changed_parent_recomputes(self):
        cache = SignatureDigestCache()
        keys = [("a",)]
        cache.digest(keys, original)
        self.assertEqual(cache.digest(keys, lambda keys: "changed"), "changed")
        self.assertEqual(cache.summary()["hits"], 0)

    def test_large_tree_falls_back(self):
        self.assertFalse(deeply_immutable((1,) * 100001))


if __name__ == '__main__':
    unittest.main()
