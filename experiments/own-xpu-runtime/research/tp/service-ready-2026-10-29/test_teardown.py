#!/usr/bin/env python3
"""CPU unit test of the lab adapter's per-card teardown check (service-ready-2026-10-29 step 1).

Uses the real rank receipts of the e2e suite (arm A: one card per rank; arm C: two cards per rank, the receipts that
the sealed P195 check rejected as "rank teardown failure"), then mutations of them, then Transport.close with the base
close stubbed (the base's own close needs live rank processes). Run: python3 -B test_teardown.py"""
import copy, json, os, sys, tempfile, types, unittest
from pathlib import Path

D = Path(__file__).resolve().parent
E2E = D.parent / 'e2e-suite-2026-10-29/results'
sys.dont_write_bytecode = True
os.environ.pop('SC117_RANK_BDFS', None)
import importlib.util
spec = importlib.util.spec_from_file_location('lab_adapter6_tp', D / 'lab/adapter6_tp.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)


def receipts(arm):
    summary = json.loads((E2E / f'arm-{arm}/ranks-summary.json').read_text())
    rows = {int(k[-1]): v['receipt.json'] for k, v in summary.items() if k.endswith(('rank0', 'rank1'))}
    assert sorted(rows) == [0, 1]
    return rows


def base_check(r, rank, returncode):  # the sealed P195 expression (pipeline.py line 444), verbatim
    return (returncode == 0 and r["passed"] and r.get("rank") == rank and len(r["teardown"]) == 1
            and all(t["safe_to_exit"] and not t["in_flight"] and not t["live_bytes"] for t in r["teardown"]))


class RankTeardown(unittest.TestCase):
    C = receipts('C'); ONE = receipts('A')

    def test_real_receipts(self):
        for rank in (0, 1):
            self.assertTrue(A.rank_teardown_ok(self.C[rank], rank, 0, 2))      # TP rank: one record per card
            self.assertFalse(base_check(self.C[rank], rank, 0))                # reproduces the arm-C incident
            self.assertFalse(A.rank_teardown_ok(self.C[rank], rank, 0, 1))     # two records on a one-card rank
            self.assertTrue(A.rank_teardown_ok(self.ONE[rank], rank, 0, 1))    # one-card rank: unchanged outcome
            self.assertTrue(base_check(self.ONE[rank], rank, 0))
            self.assertFalse(A.rank_teardown_ok(self.ONE[rank], rank, 0, 2))   # a card's record missing
            self.assertFalse(A.rank_teardown_ok(self.C[rank], 1 - rank, 0, 2)) # wrong rank

    def test_mutations(self):
        bad = dict(status='incomplete', exit_code=1, safe_to_exit=False, in_flight=1, live_bytes=4096, error='x',
                   backend='host')
        for rank in (0, 1):
            for card in (0, 1):
                for key, value in bad.items():
                    r = copy.deepcopy(self.C[rank]); r['teardown'][card][key] = value
                    self.assertFalse(A.rank_teardown_ok(r, rank, 0, 2), (rank, card, key))
                    r = copy.deepcopy(self.C[rank]); del r['teardown'][card][key]
                    self.assertFalse(A.rank_teardown_ok(r, rank, 0, 2), (rank, card, key, 'missing'))
                r = copy.deepcopy(self.C[rank]); del r['teardown'][card]
                self.assertFalse(A.rank_teardown_ok(r, rank, 0, 2))           # missing record
                r = copy.deepcopy(self.C[rank]); r['teardown'][1 - card] = copy.deepcopy(r['teardown'][card])
                self.assertFalse(A.rank_teardown_ok(r, rank, 0, 2))           # duplicated card, other card missing
            r = copy.deepcopy(self.C[rank]); r['teardown'].append(copy.deepcopy(r['teardown'][0]))
            self.assertFalse(A.rank_teardown_ok(r, rank, 0, 2))               # extra record
            self.assertFalse(A.rank_teardown_ok(r, rank, 0, 3))               # card 0 twice, card 2 missing
            r = copy.deepcopy(self.C[rank]); r['teardown'].reverse()
            self.assertTrue(A.rank_teardown_ok(r, rank, 0, 2))                # order does not matter
            for key, value in (('passed', False), ('teardown', None), ('teardown', {})):
                r = copy.deepcopy(self.C[rank]); r[key] = value
                self.assertFalse(A.rank_teardown_ok(r, rank, 0, 2), key)
            for rc in (1, -15, None):
                self.assertFalse(A.rank_teardown_ok(self.C[rank], rank, rc, 2), rc)
            self.assertFalse(A.rank_teardown_ok(self.C[rank], rank, 0, 0))
            self.assertFalse(A.rank_teardown_ok(None, rank, 0, 2))


class Close(unittest.TestCase):
    """Transport.close: the base close stubbed to end exactly as the sealed one does (closed, then the receipt check)."""

    def run_close(self, rank_cards, arm_receipts, success=True, base_error=None, returncodes=(0, 0)):
        calls = []
        def fake_base_close(self_, ok):
            calls.append(ok)
            if base_error is not None:
                raise base_error
            self_.closed = True
            if ok:
                for rank, p in enumerate(self_.children):
                    r = json.loads((self_.out / f'rank{rank}/receipt.json').read_text())
                    A.require(base_check(r, rank, p.returncode), 'rank teardown failure')
        saved = (A.BASE.Transport.close, A.RANK_BDFS)
        A.BASE.Transport.close = fake_base_close; A.RANK_BDFS = rank_cards
        try:
            with tempfile.TemporaryDirectory() as tmp:
                t = A.Transport.__new__(A.Transport)
                t.closed = False; t.out = Path(tmp)
                t.children = [types.SimpleNamespace(returncode=rc) for rc in returncodes]
                for rank in (0, 1):
                    (t.out / f'rank{rank}').mkdir()
                    (t.out / f'rank{rank}/receipt.json').write_text(json.dumps(arm_receipts[rank]))
                t.close(success)
                again = len(calls); t.close(success)                          # a closed transport returns at once
                self.assertEqual(len(calls), again)
                return t
        finally:
            A.BASE.Transport.close, A.RANK_BDFS = saved

    TP = (('0000:23:00.0', '0000:27:00.0'), ('0000:43:00.0', '0000:47:00.0'))
    TWO = (('0000:23:00.0',), ('0000:47:00.0',))

    def test_tp_ranks_close_clean(self):
        self.assertTrue(self.run_close(self.TP, RankTeardown.C).closed)

    def test_one_card_ranks_close_clean(self):
        self.assertTrue(self.run_close(self.TWO, RankTeardown.ONE).closed)

    def test_mixed_layout(self):  # one TP rank, one one-card rank
        self.run_close((self.TP[0], self.TWO[1]), {0: RankTeardown.C[0], 1: RankTeardown.ONE[1]})
        with self.assertRaisesRegex(ValueError, 'rank teardown failure'):
            self.run_close((self.TP[0], self.TWO[1]), {0: RankTeardown.C[0], 1: RankTeardown.C[1]})

    def test_failures_still_fail(self):
        with self.assertRaisesRegex(ValueError, 'rank teardown failure'):   # TP receipts on a one-card layout
            self.run_close(self.TWO, RankTeardown.C)
        with self.assertRaisesRegex(ValueError, 'rank teardown failure'):   # a TP rank lost a card's record
            self.run_close(self.TP, {0: RankTeardown.C[0], 1: RankTeardown.ONE[1]})
        with self.assertRaisesRegex(ValueError, 'rank teardown failure'):   # nonzero exit
            self.run_close(self.TP, RankTeardown.C, returncodes=(0, 1))
        bad = copy.deepcopy(RankTeardown.C); bad[1]['teardown'][1]['live_bytes'] = 65536
        with self.assertRaisesRegex(ValueError, 'rank teardown failure'):
            self.run_close(self.TP, bad)

    def test_other_errors_propagate(self):
        for error in (ValueError('rank retained for coordinator after bounded drain'), OSError('ownership'),
                      RuntimeError('drain')):
            with self.assertRaises(type(error)) as caught:
                self.run_close(self.TP, RankTeardown.C, base_error=error)
            self.assertIs(caught.exception, error)
        # the base's teardown error before closing (not reachable in the sealed base) is not swallowed either
        with self.assertRaisesRegex(ValueError, 'rank teardown failure'):
            self.run_close(self.TP, RankTeardown.C, base_error=ValueError('rank teardown failure'))

    def test_failure_close_does_not_check_receipts(self):
        t = self.run_close(self.TWO, RankTeardown.C, success=False)
        self.assertTrue(t.closed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
