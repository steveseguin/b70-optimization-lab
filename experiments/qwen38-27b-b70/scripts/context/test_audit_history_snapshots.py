"""CPU-only auditor regressions. Subprocess fixture isolates bare engine imports."""
import hashlib
import json
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import unittest

import audit_history_snapshots as audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def fixture(self,arm='archive',mode='history',behavior='normal'):
        out=self.root/(arm+mode+behavior)
        script=r'''
import json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import live
from test_history import HistoryStub
from tasks import load_packet
engine=Path(sys.argv[1]);out=Path(sys.argv[2]);arm,mode,behavior=sys.argv[3:]
data=engine.parents[2]/'data/2026-10-07-context-semantic-development'
task=load_packet(data/'documents.json',data/'adjudicated.json')[0]
client=HistoryStub(task,behavior if behavior in ('wrong','reject-first','reject-all','forever') else 'history')
if behavior=='gap':
 with patch.object(live.SnapshotStore,'save',side_effect=live.SnapshotStorageError('disk failed')):
  try:live.run_trial(task,arm,out,client,retrieval_mode=mode)
  except live.InfrastructureError:pass
else:live.run_trial(task,arm,out,client,retrieval_mode=mode)
(out/'audit-task.json').write_text(json.dumps(task))
'''
        subprocess.run([sys.executable,'-c',script,str(audit.ENGINE),str(out),arm,mode,behavior],check=True,capture_output=True,text=True)
        return out,json.loads((out/'audit-task.json').read_bytes())

    def read(self,out):return json.loads((out/'result.json').read_bytes())
    def write(self,out,result): (out/'result.json').write_text(json.dumps(result))
    def rebind(self,out,result,name):
        result['artifacts'][name]['sha256']=hashlib.sha256((out/name).read_bytes()).hexdigest()

    def test_both_arms_modes_pass_without_quality_claim(self):
        for arm in ('archive','quoted'):
            for mode in ('history','source-only'):
                out,task=self.fixture(arm,mode)
                report=audit.audit(out,task)
                self.assertTrue(report['integrity_passed'],report)
                self.assertTrue(report['complete_snapshot_evidence'])
                self.assertIsNone(report['quality_passed'])

    def test_wrong_extra_missing_archive_states_are_not_corrected(self):
        out,task=self.fixture(behavior='wrong');report=audit.audit(out,task)
        self.assertTrue(report['integrity_passed'],report)
        self.assertFalse(self.read(out)['all_checkpoint_states_exact'])

    def test_rejected_attempts_and_model_failure_preserved(self):
        for behavior in ('reject-first','reject-all','forever'):
            out,task=self.fixture(behavior=behavior);report=audit.audit(out,task)
            self.assertTrue(report['integrity_passed'],report)
            self.assertEqual(report['complete_snapshot_evidence'],behavior!='reject-all')

    def test_post_apply_write_gap_is_explicit_not_quality_pass(self):
        for arm in ('archive','quoted'):
            out,task=self.fixture(arm,behavior='gap');report=audit.audit(out,task)
            self.assertTrue(report['integrity_passed'],report)
            self.assertFalse(report['complete_snapshot_evidence'])
            self.assertEqual(report['snapshot_write_gaps'],[{'batch_id':1,'quoted_apply_committed':arm=='quoted'}])
            self.assertIsNone(report['quality_passed'])

    def test_missing_extra_and_changed_snapshot_fail(self):
        for mutation in ('delete','extra','change'):
            out,task=self.fixture(behavior=mutation)
            path=out/'snapshots/batch-2.json'
            if mutation=='delete':path.unlink()
            elif mutation=='extra':(out/'snapshots/unexpected').write_text('x')
            else:path.write_text('{}')
            self.assertFalse(audit.audit(out,task)['integrity_passed'])

    def test_rebinding_artifact_hash_does_not_hide_wrong_snapshot(self):
        out,task=self.fixture();result=self.read(out);name='snapshots/batch-1.json'
        record=json.loads((out/name).read_bytes());record['state']['new key']=999
        (out/name).write_text(json.dumps(record));self.rebind(out,result,name);self.write(out,result)
        report=audit.audit(out,task)
        self.assertFalse(report['integrity_passed']);self.assertIn('raw accepted state',str(report['issues']))

    def test_cache_and_raw_call_tampering_fail_even_with_rebound_hash(self):
        for target in ('cache','calls'):
            out,task=self.fixture(behavior=target);result=self.read(out)
            if target=='cache':
                name='answer-session.json';session=json.loads((out/name).read_bytes())
                first=next(v for k,v in session['cache'].items() if k.startswith('state_at:'))
                first['state']['fabricated']=123
                (out/name).write_text(json.dumps(session));result['answer_protocol']=session
            else:
                name='calls.jsonl';calls=audit.lines(out/name)
                reply=json.loads(calls[0]['response']);reply['state']['fabricated']=123
                calls[0]['response']=json.dumps(reply)
                (out/name).write_text(''.join(json.dumps(c)+'\n' for c in calls))
            self.rebind(out,result,name);self.write(out,result)
            self.assertFalse(audit.audit(out,task)['integrity_passed'])

    def test_task_hash_count_and_source_mode_tampering_fail(self):
        for target in ('task','count','mode'):
            out,task=self.fixture(behavior=target);result=self.read(out)
            if target=='task':task['batches'][0]['text']+=' changed'
            elif target=='count':result['snapshot_count']=True
            else:result['retrieval_mode']='invalid'
            self.write(out,result)
            self.assertFalse(audit.audit(out,task)['integrity_passed'])

    def test_recorded_sqlite_state_must_match_fresh_raw_reply_replay(self):
        out,task=self.fixture('quoted')
        with sqlite3.connect(out/'canonical.sqlite') as db:
            db.execute("UPDATE current_state SET value='999999'")
        report=audit.audit(out,task)
        self.assertFalse(report['integrity_passed']);self.assertIn('SQLite state',str(report['issues']))

    def test_source_response_and_chain_hashes_are_independently_bound(self):
        for field in ('source_text_sha256','raw_response_sha256','previous_snapshot_sha256'):
            out,task=self.fixture(behavior=field);result=self.read(out);name='snapshots/batch-2.json'
            record=json.loads((out/name).read_bytes());record['receipt'][field]='0'*64
            (out/name).write_text(json.dumps(record));self.rebind(out,result,name);self.write(out,result)
            report=audit.audit(out,task)
            self.assertFalse(report['integrity_passed']);self.assertIn('provenance',str(report['issues']))

    def test_cache_query_never_issued_in_raw_answer_calls_is_rejected(self):
        out,task=self.fixture();result=self.read(out);name='answer-session.json'
        session=json.loads((out/name).read_bytes())
        key=next(k for k in session['cache'] if k.startswith('state_at:'))
        response=session['cache'].pop(key)
        session['cache']['state_at:'+json.dumps({'batch_id':2,'counters':None},sort_keys=True,separators=(',',':'))]=response
        (out/name).write_text(json.dumps(session));result['answer_protocol']=session
        self.rebind(out,result,name);self.write(out,result)
        report=audit.audit(out,task)
        self.assertFalse(report['integrity_passed']);self.assertIn('never requested',str(report['issues']))

    def test_refused_attempt_trace_must_still_match_raw_output(self):
        out,task=self.fixture(behavior='reject-first');result=self.read(out);name='trace.json'
        trace=json.loads((out/name).read_bytes())
        trace['batches'][0]['attempts'][0]['response']['memory']='different rejected response'
        (out/name).write_text(json.dumps(trace));result['batches']=trace['batches']
        self.rebind(out,result,name);self.write(out,result)
        report=audit.audit(out,task)
        self.assertFalse(report['integrity_passed']);self.assertIn('trace response differs',str(report['issues']))


if __name__=='__main__':unittest.main()
