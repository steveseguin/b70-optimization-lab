"""Reject forged acceptance flags, truncated responses and replacement ownership."""
import importlib.util
import json
from pathlib import Path
import tarfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('tp2_acceptance',ROOT/'experiments/qwen38-27b-b70/scripts/collect-fp8-tp2-acceptance-evidence.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)

class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tarfile.open(MODULE.DEFAULT/'evidence.tar.gz') as archive:
            cls.files={item.name:archive.extractfile(item).read() for item in archive}

    def test_frozen_acceptance_recomputes(self):
        self.assertTrue(MODULE.derive(self.files)['passed'])

    def test_replacement_container_is_not_owned(self):
        files=self.files.copy();name='run/session/stop-request.json';receipt=json.loads(files[name]);receipt['container_id']='a'*64;files[name]=json.dumps(receipt).encode()
        result=MODULE.derive(files)
        self.assertFalse(result['gates']['owned_clean_stop']);self.assertFalse(result['passed'])

    def test_passed_flags_cannot_hide_wrong_answer(self):
        files=self.files.copy();name='run/practical/summary.json';summary=json.loads(files[name]);summary['rows'][0]['text']='{"day":"Friday","shelter":"B","guests":6,"vegetarian":true}';files[name]=json.dumps(summary).encode()
        result=MODULE.derive(files)
        self.assertFalse(result['gates']['practical_token_repeat_exact']);self.assertFalse(result['passed'])

    def test_truncated_raw_response_is_rejected(self):
        files=self.files.copy();name='run/practical/1-conversation/response.sse';files[name]=files[name].replace(b'data: [DONE]',b': missing done')
        with self.assertRaisesRegex(ValueError,'missing \\[DONE\\]'):MODULE.derive(files)

if __name__=='__main__':unittest.main()
