"""Every selection crosses real dispatch and explicit record-tool refusals."""
import json,unittest,runpy
from pathlib import Path
import bundle_selection as bundle
import merge_dispatch
import p49_dispatch
import p49d_k2
import packet56_submission

class Consumers(unittest.TestCase):
    def test_all_choices_dispatch_and_record_boundaries(self):
        dispatch=json.loads((Path(__file__).parent/'dispatch-speed6.json').read_text())
        for name in bundle.VIEWS:
            with self.subTest(name=name):
                selected=bundle.selection(name)
                merged,_=merge_dispatch.merge([dispatch,dispatch])
                self.assertEqual(merged,dispatch)
                for consume in (
                    lambda:p49_dispatch.pin_production_dispatch('/unused',{},round3_root='/unused'),
                    lambda:p49d_k2.measured_coverage('/unused',selected),
                    lambda:packet56_submission.validate_bundle({},selected)):
                    with self.assertRaisesRegex(ValueError,'micro/screen-only'):consume()
    def test_legacy_chain_entrypoints_refuse_before_imports(self):
        for name in bundle.VIEWS:
            for script in ('queue_runner.py','window.py','resume_chain.py'):
                with self.subTest(name=name,script=script):
                    with self.assertRaisesRegex(ValueError,'micro/screen-only'):
                        runpy.run_path(str(Path(__file__).parent/script),init_globals={'selection':bundle.selection(name)})
    def test_submission_cli_refuses_before_any_external_action(self):
        with self.assertRaisesRegex(ValueError,'micro/screen-only'):packet56_submission.main([])
if __name__=='__main__':unittest.main()
