"""Real route-inventory guards under digest reuse, plus launch/evidence scope."""
import copy
import unittest
import test_candidate_safety as fixtures
from test_candidate_safety import expected, cs, SafetyRefusal
from signature_cache127 import SignatureDigestCache
import stream_contract as c
from test_gate_receipts import passing, decide
import stream_receipts

OPTIONS = dict(snapshot_mode='fingerprint', snapshot_schedule='full', display_worker='serial',
    display_device='xpu:3', aux_residency='legacy', display_schedule='sampler-a', anchor_read_ahead=0)

class CachedRoutes(unittest.TestCase):
    def test_real_snapshot_equal_and_mutations_still_refuse(self):
        capture, gate, model = fixtures.LiveSnapshot().build()
        cache = SignatureDigestCache()
        digest = lambda keys: cache.digest(keys, cs._signature_digest)
        parent = cs.snapshot_routes(capture, gate, model)
        self.assertEqual(parent, cs.snapshot_routes(capture, gate, model, digest))
        self.assertEqual(parent, cs.snapshot_routes(capture, gate, model, digest))
        self.assertGreater(cache.summary()['hits'], 0)
        exp = expected(frozen=True, sigs={r['index']: r['signature_digest'] for r in parent['registry']})
        capture.CAPTURES_FROZEN[0] = True
        cs.check_route_inventory(cs.snapshot_routes(capture, gate, model, digest), exp)
        route = capture._ROUTES[10]
        owner = next(iter(route.entries))
        old = dict(route.entries[owner])
        route.entries[owner] = {('changed',): 1, ('other',): 2}
        with self.assertRaises(SafetyRefusal):
            cs.check_route_inventory(cs.snapshot_routes(capture, gate, model, digest), exp)
        route.entries[owner] = old
        route.entries[777] = {('foreign',): 1}
        with self.assertRaises(SafetyRefusal):
            cs.check_route_inventory(cs.snapshot_routes(capture, gate, model, digest), exp)

    def test_off_is_parent_and_enable_is_one_shot(self):
        adapter = object.__new__(cs.CandidateAdapter)
        adapter.enable_signature_digest_cache(0)
        self.assertEqual(adapter.signature_cache_summary(), {'enabled': False, 'stats': None})
        with self.assertRaises(SafetyRefusal): adapter.enable_signature_digest_cache(1)

class Scope(unittest.TestCase):
    def scope(self, enabled=1, frames=145, options=None):
        c.check_snapshot_digest_scope(enabled, frames, 'two-way20-28', 'frame', 0,
            ('cone',1,1), OPTIONS if options is None else options)

    def test_parse(self):
        self.assertEqual(c.launch_snapshot_digest_cache({}),0)
        self.assertEqual(c.launch_snapshot_digest_cache({'LTX_SNAPSHOT_DIGEST_CACHE':'1'}),1)
        for bad in (True,1,None,'true',' 1','2'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                c.launch_snapshot_digest_cache({'LTX_SNAPSHOT_DIGEST_CACHE':bad})

    def test_all_scope_fields(self):
        self.scope()
        self.scope(0,49,{})
        for k in OPTIONS:
            with self.subTest(k=k),self.assertRaises(ValueError):
                self.scope(options=dict(OPTIONS,**{k:None}))
        for bad in (True,1.,'1',None,2):
            with self.subTest(bad=bad),self.assertRaises(ValueError): self.scope(bad)
        with self.assertRaises(ValueError):self.scope(frames=169)

    def test_receipt_option_and_three_chain_mismatch(self):
        rows, decodes, captures = passing(frames=145, anchor='frame',decoder_graph=0,
            levers=('cone',1,1),snapshot_mode='fingerprint')
        for r in rows:
            r['server_options'].update(OPTIONS,snapshot_digest_cache=1,
                residency_qualification_id=c.residency_qualification_id(r['qualification_id'],'legacy'))
            stream_receipts.validate_measurements(r)
        for d in decodes.values():
            d.update(display_worker='serial', completion_worker='serial',
                display_worker_timing={'queued_ns':None,'start_ns':None,'gated_inline':d['kind'] in c.GATED_KINDS})
        # Residency identity is separately required when auxiliary option is explicit.
        # Fixture supplies it; all option values must match every chain.
        result = decide(rows,decodes,captures,frames=145,anchor='frame',decoder_graph=0,levers=('cone',1,1))
        self.assertTrue(result['passed'],result['failures'])
        rows[4]['server_options']['snapshot_digest_cache']=0
        self.assertFalse(decide(rows,decodes,captures,frames=145,anchor='frame',decoder_graph=0,levers=('cone',1,1))['passed'])
