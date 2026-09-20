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

    def sources(self):
        return json.loads((MODULE.DEFAULT/'manifest.json').read_text())['sources']

    def drift(self):
        path=MODULE.DEFAULT/MODULE.DRIFT_FILE
        return {e['path']:e for e in json.loads(path.read_text())['entries']} if path.exists() else {}

    def test_declared_source_drift_is_proved_and_reported_as_pending(self):
        pending=MODULE.check_sources(self.sources(),self.drift(),self.files)
        self.assertTrue(all(e['acceptance']=='pending' and e['reason'] and e['retire_by'] for e in pending))

    def test_undeclared_source_drift_still_fails(self):
        declared=self.drift()
        if not declared:self.skipTest('no source has drifted from this packet')
        for path in declared:
            with self.subTest(path=path),self.assertRaisesRegex(AssertionError,'nothing declares the change'):
                MODULE.check_sources(self.sources(),{k:v for k,v in declared.items() if k!=path},self.files)

    def test_drift_entry_cannot_hide_a_second_change(self):
        declared=self.drift()
        entry=declared.get('packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py')
        if not entry:self.skipTest('the two-card launcher has not drifted from this packet')
        faked=json.loads(json.dumps(entry));faked['proof']['differences']=[]
        with self.assertRaisesRegex(AssertionError,'but source-drift.json declares'):
            MODULE.check_sources(self.sources(),dict(declared,**{faked['path']:faked}),self.files)

    def test_unchanged_definitions_proof_catches_an_edited_gate(self):
        entry={'path':'x.py','proof':{'kind':'unchanged_definitions','definitions':['derive']}}
        MODULE.prove_unchanged(entry,b'def derive(files):\n    return 1\n',b'def derive(files):\n    return 1\n')
        with self.assertRaisesRegex(AssertionError,'declared unchanged but its source differs'):
            MODULE.prove_unchanged(entry,b'def derive(files):\n    return 1\n',b'def derive(files):\n    return 2\n')

    def test_additive_proof_rejects_a_rewritten_line(self):
        entry={'path':'x.py','proof':{'kind':'additive','additive':['main']}}
        frozen=b'def main():\n    a = 1\n    return a\n'
        MODULE.prove_additive(entry,frozen,b'def main():\n    a = 1\n    log(a)\n    return a\n')
        with self.assertRaisesRegex(AssertionError,'rewritten or removed'):
            MODULE.prove_additive(entry,frozen,b'def main():\n    a = 2\n    return a\n')
        with self.assertRaisesRegex(AssertionError,'does not declare it additive'):
            MODULE.prove_additive({'path':'x.py','proof':{'kind':'additive','additive':[]}},frozen,
                                  b'def main():\n    a = 1\n    log(a)\n    return a\n')

    def test_truncated_raw_response_is_rejected(self):
        files=self.files.copy();name='run/practical/1-conversation/response.sse';files[name]=files[name].replace(b'data: [DONE]',b': missing done')
        with self.assertRaisesRegex(ValueError,'missing \\[DONE\\]'):MODULE.derive(files)

if __name__=='__main__':unittest.main()
