"""Packet134 explicit graph-off169 admission, full native display reserve, parent parity."""
import copy
import unittest
import text_residency133 as text
import stream_contract as contract
import runtime_packet as packet
from unittest.mock import patch

def env():
    return dict(packet.CONTROL_ENVIRONMENT, **dict(text.SCOPE,
        LTX_STREAM_FRAMES='169', LTX_DECODER_GRAPH='0', LTX_CONE_GRAPH_MEMORY='off'),
        LTX_TEXT_RESIDENCY='split36', LTX_CHUNK_ARM='split36-169',
        LTX_GC_INTERVAL_SECONDS='60', LTX_MAINTENANCE_MODE='idle',
        LTX_SNAPSHOT_DIGEST_CACHE='1', LTX_STORAGE_SCAN_MODE='background')

def options():
    return dict(text.options(env()), cone_graph_memory='off', audio_residency='legacy',
        cone_capture_reserve='parent', aux_residency='legacy', display_device='xpu:3',
        display_schedule='eager-display', display_worker='serial', anchor_read_ahead=0,
        snapshot_schedule='full', snapshot_mode='fingerprint', display_allocator_release='off',
        decoder_graph_pool_cap_bytes=None)

class Chunk134(unittest.TestCase):
    def test_on_is169_eager(self):
        self.assertEqual(text.validate_scope(env()), 'split36')
        o=options()
        contract.check_text_residency_scope(169,'two-way20-28','frame',0,('cone',1,1),o)
        contract.check_residency_scope(169,'two-way20-28','frame',0,'cone','legacy','xpu:3','off','split36-169')
        self.assertFalse(contract.cone_memory_scope(169,'two-way20-28','frame',0,('cone',1,1),o))
    def test_all_launch_guards(self):
        with patch.dict('os.environ',env(),clear=True): packet.check_control_environment()
    def test_same_maintenance_and_digest_scope(self):
        a=(169,'two-way20-28','frame',0,('cone',1,1),options())
        contract.check_gc_scope(60,*a)
        contract.check_snapshot_digest_scope(1,*a)
        contract.check_maintenance_scope('idle',*a)
    def test_graph169_refused(self):
        bad=dict(env(),LTX_DECODER_GRAPH='1',LTX_CONE_GRAPH_MEMORY='text-shift')
        with self.assertRaises(ValueError):text.validate_scope(bad)
    def test_unknown_arm_refused(self):
        for value in ('',None,0,'169','split36-145'):
            with self.assertRaises(ValueError):text.validate_scope(dict(env(),LTX_CHUNK_ARM=value))
    def test169_needs_explicit_arm(self):
        with self.assertRaises(ValueError):text.validate_scope(dict(env(),LTX_CHUNK_ARM='off'))
    def test_native_display_full_reserve_boundary(self):
        need=65*2**28
        self.assertEqual(text.display_admission(need,before=True)['margin_bytes'],0)
        self.assertEqual(text.display_admission(need,before=True)['transient_reserve_bytes'],13*2**29)
        with self.assertRaises(ValueError):text.display_admission(need-1,before=True)
    def test_native_display_after_floor_and_band(self):
        need=39*2**28
        self.assertEqual(text.display_admission(need,before=False)['margin_bytes'],0)
        with self.assertRaises(ValueError):text.display_admission(need-1,before=False)
    def test_display_evidence_all_phases(self):
        evidence={p:text.display_admission(20*2**30,before=b) for p,b in (('before',True),('after',False))}
        self.assertTrue(text.validate_display_evidence(options(),{'native_display_memory134':evidence}))
        with self.assertRaises(ValueError):text.validate_display_evidence(options(),{})
        with self.assertRaises(ValueError):text.validate_display_evidence({}, {'native_display_memory134':evidence})
        for phase in evidence:
            for key in evidence[phase]:
                bad=copy.deepcopy(evidence);bad[phase][key]='changed'
                with self.assertRaises(ValueError):text.validate_display_evidence(options(),{'native_display_memory134':bad})
    def test_name_binds_arm(self):
        self.assertTrue(packet.expected_run_name(env()).endswith('-textsplit36-armsplit36-169'))
    def test_parent_numerical_ids_preserved(self):
        self.assertEqual(packet.QIDS,packet.PARENT_QIDS)
    def test_off_text_scope_preserved(self):
        self.assertEqual(text.validate_scope(dict(text.SCOPE,LTX_TEXT_RESIDENCY='split36')),'split36')
        self.assertEqual(text.options({}),dict(text_residency='legacy',text_oracle_sha256=None))

for key in text.SCOPE:
    def test(self,key=key):
        bad=env();bad[key]='changed'
        with self.assertRaises(ValueError):text.validate_scope(bad)
    setattr(Chunk134,'test_env_refuses_'+key.lower(),test)
for key in options():
    def test(self,key=key):
        bad=options();bad[key]='changed'
        with self.assertRaises(ValueError):contract.check_text_residency_scope(169,'two-way20-28','frame',0,('cone',1,1),bad)
    setattr(Chunk134,'test_options_refuse_'+key,test)
