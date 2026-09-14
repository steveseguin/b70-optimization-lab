import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('candidate_run',Path(__file__).with_name('run.py'))
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)

class CycleTests(unittest.TestCase):
    def cycle(self,guard):
        results=[]
        for command in ['A','B']*3:
            guard.before(command)
            results.append(guard.observe(command,{'returncode':0,'output':'exact\n'}))
        return results
    def test_warn_after_three_exact_cycles_stop_before_next_execution(self):
        g=R.ExactTwoCommandCycleGuard();results=self.cycle(g)
        self.assertTrue(all('warning' not in r['output'] for r in results[:5]))
        self.assertIn('Repetition warning',results[-1]['output'])
        with self.assertRaisesRegex(RuntimeError,'Two-command cycle restarted'):g.before('A')
    def test_changed_output_or_exit_code_prevents_detection(self):
        for field,value in [('output','different'),('returncode',1)]:
            g=R.ExactTwoCommandCycleGuard()
            for i,command in enumerate(['A','B']*3):
                r={'returncode':0,'output':'exact\n'}
                if i==3:r[field]=value
                g.before(command);g.observe(command,r)
            self.assertEqual(g.warnings,0);g.before('A')
    def test_full_command_not_prefix(self):
        g=R.ExactTwoCommandCycleGuard()
        for c in ['python edit A','python edit B','python edit A','python edit B','python edit A','python edit C']:
            g.before(c);g.observe(c,{'returncode':0,'output':''})
        self.assertEqual(g.warnings,0)
    def test_different_next_action_resets_pending_cycle(self):
        g=R.ExactTwoCommandCycleGuard();self.cycle(g)
        g.before('C');g.observe('C',{'returncode':0,'output':''});g.before('A')
        self.assertIsNone(g.pending_command);self.assertEqual(len(g.history),1)
    def test_single_command_not_reclassified(self):
        g=R.ExactTwoCommandCycleGuard()
        for _ in range(6):g.before('A');g.observe('A',{'returncode':0,'output':''})
        self.assertEqual(g.warnings,0)
    def test_finish_still_runs_acceptance_after_warning(self):
        class Submitted(Exception):pass
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'workspace').mkdir();calls=[]
            class Sandbox:
                run_dir=root;stopped=False
                def execute(self,action):
                    calls.append(action['command'])
                    if action['command']==R.FINISH:raise Submitted()
                    return {'returncode':0,'output':'exact\n'}
            env=R.CheckedEnvironment(Sandbox(),'acceptance',root,3)
            for c in ['A','B']*3:env.execute({'command':c})
            with self.assertRaises(Submitted):env.execute({'command':R.FINISH})
            self.assertEqual(calls[-2:],['acceptance',R.FINISH]);self.assertTrue(env.validations[-1]['accepted'])
    def test_environment_stops_without_seventh_tool_call(self):
        calls=[]
        class Sandbox:
            def execute(self,action):
                calls.append(action['command']);return {'returncode':0,'output':'exact\n'}
        env=R.CheckedEnvironment(Sandbox(),'unused',Path('/unused'),3)
        for c in ['A','B']*3:env.execute({'command':c})
        with self.assertRaisesRegex(RuntimeError,'Two-command cycle restarted'):env.execute({'command':'A'})
        self.assertEqual(len(calls),6);self.assertEqual(env.loop_warnings,1)


class ReplayEvidenceTests(unittest.TestCase):
    def test_full_observation_preserved_and_action_must_match_answer(self):
        import replay_cycle_guard as replay
        command='python3 - <<\'PY\'\nprint("a")\nPY'
        output='line one\n\nline three\n'
        trajectory={'messages':[
            {'role':'assistant','content':'```bash\n'+command+'\n```','extra':{'actions':[{'command':command}]}},
            {'role':'user','content':'<tool_response>\nExit status: 0\nOutput:\n'+output+'\n</tool_response>'}]}
        self.assertEqual(replay.exact_records(trajectory)[0]['observation']['output'],output)
        trajectory['messages'][0]['extra']['actions'][0]['command']='echo different'
        with self.assertRaisesRegex(ValueError,'differs from final-answer'):
            replay.exact_records(trajectory)

    def test_compact_trace_tamper_rejected_even_with_updated_capture_hash(self):
        import hashlib
        import json
        import shutil
        import subprocess
        import sys
        worker=Path(__file__).resolve().parent
        evidence=worker.parent/'experiments/local-coding-worker/data/2026-09-14-worker-hardening/cycle'
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)
            for name in ('traces.json','report.json','capture.json'):
                shutil.copyfile(evidence/name,destination/name)
            traces=json.loads((destination/'traces.json').read_text())
            traces[0]['records'][0]['observation']['output']='forged output'
            data=(json.dumps(traces)+'\n').encode();(destination/'traces.json').write_bytes(data)
            capture=json.loads((destination/'capture.json').read_text())
            capture['traces_sha256']=hashlib.sha256(data).hexdigest()
            (destination/'capture.json').write_text(json.dumps(capture))
            result=subprocess.run([sys.executable,str(worker/'replay_cycle_guard.py'),'--verify','--out',str(destination)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('compact traces differ from frozen source records',result.stderr)
