"""Census admission cannot bypass the fresh smoke or its real stream parser."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import analyze
import coordinator_gate as C
import queue_runner as Q
import verify_ready as V
import window as W
import suite_driver as D
import test_first_request

class CensusReady(unittest.TestCase):
    def test_proposals_separate_and_arm_bound(self):
        smoke, = C.proposal_jobs(C.PROPOSAL)
        census, = C.proposal_jobs(C.CENSUS_PROPOSAL)
        self.assertNotEqual(smoke['name'], census['name'])
        self.assertEqual(C.identity(smoke)[3], 'smoke')
        self.assertEqual(C.identity(census)[3], 'combined')
        self.assertEqual(C.output_root(C.PROPOSAL), C.output_root(C.CENSUS_PROPOSAL))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'queue-A.txt').write_text(json.dumps(census)+'\n')
            (root/'queue-B.txt').write_text('# empty\n')
            self.assertTrue(C.check(root,C.CENSUS_PROPOSAL)['passed'])
            with self.assertRaises(ValueError): C.check(root,C.PROPOSAL)

    def test_absent_smoke_cannot_qualify(self):
        with patch.object(W,'build_gate'), self.assertRaises(FileNotFoundError): V.verify()

    def test_real_analyzer_and_all_requests_required(self):
        # Operational envelope synthetic; analyzer and stream bytes are real.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); requests=[]
            (root/'queue.json').write_text(json.dumps(dict(passed=True, completed=list(Q.ORDER),arm='smoke')))
            for stage in Q.ORDER:
                (root/stage).mkdir()
                for leaf in ('kernel-before.jsonl','kernel-window.jsonl'):(root/stage/leaf).write_text('')
            for i in range(12):
                prompt=str(i); folder=root/'WSCREEN/run/run/S0'/prompt;folder.mkdir(parents=True)
                test_first_request.FirstRequest().fixture(folder)
                requests.append(dict(prompt_id=prompt,ttft_ms=60000))
            summary=dict(smoke_passed=True,views=[dict(requests=requests)])
            with patch.object(C,'identity',return_value=('smoke','A',str(root),'smoke')), \
                 patch.object(W,'build_gate'), patch.object(Q,'verify_success',return_value=dict(build_receipt_sha256='same',native_files={})), \
                 patch.object(W,'sha',return_value='same'), patch.object(W,'verify_files'), \
                 patch.object(analyze,'native_closure'), patch.object(D,'summarize_bracket',return_value=summary):
                self.assertEqual(len(V.verify()['streams']),12)
                requests[0]['ttft_ms']=151000
                with self.assertRaisesRegex(ValueError,'four times'):V.verify()
                requests[0]['ttft_ms']=60000
                (root/'WSCREEN/run/run/S0/11/measure.jsonl').write_text('')
                with self.assertRaisesRegex(ValueError,'empty'):V.verify()

    def test_historical_failed_device_run_is_rejected(self):
        root=Path(__file__).resolve().parent/'evidence/card0-census-c/smoke'
        if not root.exists():self.skipTest('local retained failed device evidence unavailable')
        with self.assertRaisesRegex(ValueError,'completed single load'):analyze.analyze(root)

if __name__=='__main__':unittest.main()
