"""Fast pure-CPU admission and analyzer controls; no model or device discovery."""
import copy
import unittest
from types import SimpleNamespace
from k2_probe import validate, mark
from k2_probe_analyze import samples, summarize, forecast

class Admission(unittest.TestCase):
    def args(self, **changes):
        return SimpleNamespace(**dict(dict(mtp_k2_probe=True, diagnostic_unsealed=True,
            draft_rank=1, target_split=23, context=4096, draft='mtp', draft_fault='none', window='WS'), **changes))
    def test_diagnostic_accepted(self):
        validate(self.args()); validate(self.args(), window=True)
    def test_qualifying_refused(self):
        for window in (False, True):
            with self.assertRaisesRegex(RuntimeError, 'never qualifying'):
                validate(self.args(diagnostic_unsealed=False), window=window)
    def test_wrong_config_refused(self):
        for change in (dict(draft_rank=0), dict(target_split=24), dict(context=32768),
                       dict(draft='none'), dict(draft_fault='wrong')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                validate(self.args(**change))
    def test_wrong_window_refused(self):
        for window in ('K0', 'KD', 'W0p', 'WSs'):
            with self.subTest(window=window), self.assertRaises(RuntimeError):
                validate(self.args(window=window), window=True)
    def test_inactive_does_not_change_admission(self):
        validate(self.args(mtp_k2_probe=False, diagnostic_unsealed=False, context=32768, target_split=0))
    def test_markers_and_promotion_refusal(self):
        from diagnostic_mode import reject_nonqualifying
        row=mark(dict(passed=True, qualifying=True), self.args())
        self.assertTrue(row['diagnostic_unsealed']); self.assertFalse(row['qualifying'])
        with self.assertRaises(ValueError): reject_nonqualifying(row)

class Analyzer(unittest.TestCase):
    def fixture(self):
        receipt=dict(passed=True, diagnostic_unsealed=True, qualifying=False, mtp_k2_probe=True,
                     prompt_tokens=5, tokens=[10, 11, 12, 13],
                     draft_rows=[dict(position=5+i, guess=g) for i,g in enumerate((10, 0, 12, 13))])
        probe=[]
        for i,(g1,g2) in enumerate(((10,11),(0,12),(12,0),(13,7))):
            probe.append(dict(schema='packet45.mtp-k2-probe.v1', diagnostic_unsealed=True, qualifying=False,
                g1_position=5+i, g2_position=6+i, g1=g1, g2=g2, embedding_token=g1,
                state_restored=True, hidden_source='previous-draft-pre-final-mixer-four-stream',
                context_extent_before=32, context_extent_restored=32,
                first_step_ms=2.8, extra_step_ms=3., backup_ms=9., restore_and_check_ms=11.))
        return receipt,probe
    def test_exact_denominators(self):
        rows,censored=samples(*self.fixture()); s=summarize(rows)
        self.assertEqual(censored,1);self.assertEqual(s['p_g1_all'],3/4)
        self.assertEqual(s['p_g1'],2/3);self.assertEqual(s['p_g2_given_g1'],1/2)
        self.assertEqual(s['p_g2_unconditional'],2/3);self.assertEqual(s['extra_drafter_ms_median'],3.)
    def test_forecast_excludes_diagnostic_backup(self):
        rows,_=samples(*self.fixture()); f=forecast(summarize(rows))
        self.assertAlmostEqual(f['drafter_ms'],5.8)
        self.assertAlmostEqual(f['expected_tokens_per_k2_cycle'],2.)
        self.assertAlmostEqual(f['scenarios'][0]['projected_tok_s'],2000/45.8)
        self.assertTrue(f['projected_not_measured']);self.assertFalse(f['qualifying'])
    def test_fail_closed_tampering(self):
        for key,value in (('g2_position',99),('g1',5),('embedding_token',6),('state_restored',False),
                          ('hidden_source','target'),('context_extent_restored',64),
                          ('extra_step_ms',float('nan')),('qualifying',True)):
            receipt,probe=self.fixture();probe[0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): samples(receipt,probe)
    def test_missing_and_duplicate_logs(self):
        receipt,probe=self.fixture()
        for rows in (probe[:-1],probe+[copy.copy(probe[0])],[]):
            with self.assertRaises(ValueError): samples(receipt,rows)
    def test_provider_failure_cannot_bias_acceptance(self):
        receipt,probe=self.fixture();receipt['draft_rows'][0]['provider_error']=1
        with self.assertRaises(ValueError):samples(receipt,probe)
        receipt,probe=self.fixture();receipt['draft_rows'].pop(0);probe.pop(0)
        with self.assertRaises(ValueError):samples(receipt,probe)
    def test_failed_or_qualifying_request(self):
        for key,value in (('passed',False),('qualifying',True),('diagnostic_unsealed',False)):
            receipt,probe=self.fixture();receipt[key]=value
            with self.assertRaises(ValueError): samples(receipt,probe)

if __name__=='__main__': unittest.main()
