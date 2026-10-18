"""CPU-only evidence refresh; no launcher and no live queue mutation."""
import json,sys
from source_decision import O,P,ROOT,sha,save
def test_sources():return {str(f.relative_to(ROOT)):sha(f) for f in [O/'test139.py',O/'verify_ready.py',O/'evidence_reader.py',O/'submission_evidence.py',O/'test_submission.py',O/'submission_fixture.py',P/'test_drain_fix.py',P/'test_packet124.py',P/'test_prepare_resume.py',P/'test_resume_chain.py']}
def verify_tests():
 row=json.loads((O/'cpu-tests.json').read_text());assert row['passed'] and row['sources']==test_sources();assert sha(O/'tests.log')==row['log_sha256'];return row
def main():
 from verify_ready import evaluate
 row=evaluate();save(O/'ready.json',row);print(json.dumps(row,indent=2))
if __name__=='__main__':main()
