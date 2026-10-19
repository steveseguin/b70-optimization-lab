"""Release and submission must fail closed even if saved booleans say pass."""
import copy,unittest
from unittest.mock import patch
import packet58_submission as S
import test_submission as T
class BindingTests(unittest.TestCase):
    def test_saved_winner_cannot_hide_one_slow_candidate(self):
        fixture,seal=T.synthetic()
        T.changed(fixture,'queue.json',lambda q:q['readiness'].update(rates=[20,33.1,33,33.33,33]))
        with patch.object(S,'SEAL_SHA',seal),self.assertRaisesRegex(ValueError,'numeric release'):S.derive(fixture)
    def test_saved_drift_cannot_hide_drift(self):
        fixture,seal=T.synthetic()
        T.changed(fixture,'queue.json',lambda q:q['readiness'].update(rates=[20,36,33,36,35]))
        with patch.object(S,'SEAL_SHA',seal),self.assertRaisesRegex(ValueError,'numeric release'):S.derive(fixture)
    def test_bracket_numbers_cannot_be_omitted(self):
        fixture,seal=T.synthetic();T.changed(fixture,'queue.json',lambda q:q.pop('readiness'))
        with patch.object(S,'SEAL_SHA',seal),self.assertRaisesRegex(ValueError,'bracket numbers'):S.derive(fixture)
    def test_incorrect_native_demand_mode_refused(self):
        fixture,seal=T.synthetic();name='WS128/run/run/receipt.json'
        digest=T.changed(fixture,name,lambda r:r.update(demand_variant='off'))
        T.changed(fixture,'WS128/window.json',lambda r:r['native_files'].update({'run/run/receipt.json':digest}))
        with patch.object(S,'SEAL_SHA',seal),self.assertRaises(ValueError):S.derive(fixture)
