"""145-frame end-to-end CPU fake gates; GPU reference is tested independently."""
import unittest
from test_runtime_flow import harness
import stream_contract as c
import display_replica as replica

class LongerRuntime(unittest.TestCase):
    def run145(self, *args):
        return harness('--frames','145','--anchor','frame','--stream-chunks','2',
                       '--decode-delay','0.01','--audio-delay','0.01',*args)

    def check145(self, data):
        self.assertIsNone(data.get('error'), data.get('error'))
        self.assertTrue(data['verdict']['passed'], data['verdict'])
        self.assertFalse(data['xpu_initialized'])
        self.assertEqual(data['captures'],9)
        self.assertTrue(data['geometry_record']['matches'])
        self.assertEqual(data['geometry_record']['frames'],145)
        self.assertEqual([r['delivery_new_frames'] for r in data['chunks'][-2:]],[145,144])
        self.assertTrue(all(r['anchor_decode']['equal'] for r in data['chunks'][3:]))

    def test_dg0_three_chains_geometry_and_live_anchor(self):
        self.check145(self.run145('--decoder-graph','0'))

    def test_dg0_xpu2_three_chains_and_live_anchor(self):
        data=self.run145('--decoder-graph','0',
                         '--display-device','xpu:2','--display-schedule','eager-display')
        self.check145(data)
        self.assertEqual(len(data['verdict_file']['display_replica_rows']),9)
        self.assertTrue(all(r['display_replica']['equal'] for r in data['chunks'][:9]))

    def test_new_length_measured_geometry_mismatch_halts(self):
        data=self.run145('--decoder-graph','0','--inject','geometry')
        self.assertTrue(data.get('error') or data.get('halted'))
        self.assertFalse(data.get('verdict',{}).get('passed',False))

    def test_new_length_repeat_chain_cone_mismatch_halts(self):
        data=self.run145('--decoder-graph','0','--inject','cone-repeat-diff')
        self.assertTrue(data.get('error') or data.get('halted'))
        self.assertIn('anchor-decode-118-refused.json', data['lever_latches'])

    def test_replica_length_scope(self):
        replica.validate_scope('xpu:2',145,'frame','cone','eager-display')
        replica.validate_scope('xpu:2',169,'frame','cone','eager-display')
        with self.assertRaises(RuntimeError):
            replica.validate_scope('xpu:2',193,'frame','cone','eager-display')

    def test_145_request_cannot_reuse_121_identity(self):
        a=c.qualification_id(121,'two-way20-28','frame',0)
        b=c.qualification_id(145,'two-way20-28','frame',0)
        self.assertNotEqual(a,b)
        g=c.build_chunk_graph(c.stream_params(145,0,'boat',42,'','boat',0,placement='two-way20-28',anchor='frame',decoder_graph=0))
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(g,121,'two-way20-28','frame',0)
