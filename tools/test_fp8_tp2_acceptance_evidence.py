"""Reject forged acceptance flags, truncated responses and replacement ownership."""
import hashlib
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
        faked=json.loads(json.dumps(entry))
        # Declare something other than what changed: no differences when some are declared, else a flag that did not change.
        faked['proof']['differences']=[] if entry['proof'].get('differences') else [{'flag':'--max-num-seqs','frozen':'1','current':'64'}]
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

    def test_packet_without_multi_user_stage_derives_no_multi_user_section(self):
        files={k:v for k,v in self.files.items() if not k.startswith('run/multi-user/')}  # a session without the stage
        result=MODULE.derive(files)
        self.assertNotIn('multi_user',result);self.assertNotIn('multi_user_exact_16_32_64_both_passes',result['gates'])


def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class MultiUserStageTests(unittest.TestCase):
    """derive_multi_user on a synthetic `--multi-user` session built from the working-tree runner and launcher."""

    @classmethod
    def setUpClass(cls):
        cls.runner=_load('tp2_session_for_collector',ROOT/MODULE.SESSION_RUNNER)
        cls.compare=_load('tp2_compare_for_collector',ROOT/MODULE.LADDER_COMPARATOR)
        cls.launcher=_load('tp2_launcher_for_collector',ROOT/MODULE.LAUNCHER)
        with tarfile.open(MODULE.DEFAULT/'evidence.tar.gz') as archive:
            cls.packet={item.name:archive.extractfile(item).read() for item in archive}

    def build(self,flip=False):
        reference={'oracle':{'rows':[{'prompt_id':f'p{i%8}-c{i:03d}','prompt_sha256':f'h{i}','token_ids':[i,i+1,i+2]} for i in range(64)]}}
        ref_bytes=json.dumps(reference).encode();ref_sha=hashlib.sha256(ref_bytes).hexdigest()
        runner_source=(ROOT/MODULE.SESSION_RUNNER).read_bytes()
        for suite in self.runner.MULTI_USER_SUITES.values():  # the synthetic reference stands in for the frozen one
            runner_source=runner_source.replace(suite['reference_sha256'].encode(),ref_sha.encode())
        files={'source/'+MODULE.SESSION_RUNNER:runner_source}
        for path in MODULE.MULTI_USER_DOWNLOADED_MUST_MATCH:
            files['source/'+path]=files['downloaded-source/'+path]=(ROOT/path).read_bytes()
        rows=reference['oracle']['rows']
        def ladder(key):
            batches=[]
            for repeat in (1,2):
                for users in (16,32,64):
                    selected=[dict(r,token_ids=list(r['token_ids'])) for r in rows[:users]]
                    if flip and key=='long' and (users,repeat)==(64,2):selected[40]['token_ids'][2]+=7
                    batches.append({'concurrency':users,'repeat':repeat,'rows':selected,'oracle_exact_count':users,'aggregate_tok_s_wall':12.5*users,
                                    'total_completion_tokens':3*users,'elapsed_s':0.25,'cached_tokens_all_zero':True})
            return {'oracle':{'rows':rows,'cached_tokens_all_zero':True},'batches':batches}
        suites={}
        for key in self.runner.MULTI_USER_SUITES:
            doc=ladder(key);files[f'run/multi-user/{key}-ladder.json']=json.dumps(doc).encode();files[f'reference/multi-user/{key}-ladder.json']=ref_bytes
            suites[key]=self.runner.suite_result(doc,reference,self.compare.compare_rows)
        name,identity='neural-fp8-'+'d'*32,'e'*64
        state={'schema':'neural.download.fp8-serving-state.v2','container_id':identity,'container_name':name,'model_dir':'/model-dir','state_dir':'/raw/multi-user/session',
               'port':18124,'profile':'multi-user','image_id':MODULE.EXPECTED_IMAGE,'local_image_id':MODULE.EXPECTED_IMAGE,'status':'stopped','error':None}
        argv=self.launcher.docker_argv('multi-user',Path(state['model_dir']),Path(state['state_dir']),18124,name);at=argv.index(self.launcher.IMAGE)
        env=[argv[i+1] for i in range(at) if argv[i]=='--env']
        inspect={'Id':identity,'Name':'/'+name,'Image':MODULE.EXPECTED_IMAGE,'Config':{'Cmd':argv[at+1:],'Env':env+['PATH=/usr/bin']}}
        for rel,value in (('session/state.json',state),('session/container-inspect.json',inspect),('session/stop-request.json',{'container_id':identity,'requested':True}),
                          ('session/launch.json',{'argv':argv}),('status-stopped.json',{'container_present':False,'api_healthy':False}),
                          ('summary.json',{'passed':True,'suites':suites})):
            files['run/multi-user/'+rel]=json.dumps(value).encode()
        return files

    def test_source_paths_pin_the_multi_user_overlays(self):
        for path in ('packages/qwen38-27b-fp8-tp2-b70/overlays/b70_exclusive_prefill.py','packages/qwen38-27b-fp8-tp2-b70/overlays/b70_exclusive_prefill-0.1.0.dist-info/entry_points.txt',
                     'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_decode_per_seq.py','packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_decode_per_seq-0.1.0.dist-info/entry_points.txt',
                     *MODULE.MULTI_USER_DOWNLOADED_MUST_MATCH,MODULE.SESSION_RUNNER):
            self.assertIn(path,MODULE.SOURCE_PATHS);self.assertTrue((ROOT/path).is_file(),path)

    def test_exact_stage_passes_with_totals(self):
        result=MODULE.derive_multi_user(self.build())
        self.assertTrue(result['passed'],result.get('gates') or result.get('error'))
        self.assertEqual([[p['users'],p['repeat'],p['tok_s_together']] for p in result['suites']['short']['passes']][-1],[64,2,800.0])

    def test_one_flipped_long_answer_fails(self):
        result=MODULE.derive_multi_user(self.build(flip=True))
        self.assertFalse(result['passed']);self.assertFalse(result['gates']['long_suite_exact_all_levels_both_passes'])
        self.assertTrue(result['gates']['short_suite_exact_all_levels_both_passes'])

    def test_wrong_profile_or_extra_speculation_fails_the_launch_gate(self):
        files=self.build();name='run/multi-user/session/container-inspect.json';inspect=json.loads(files[name])
        inspect['Config']['Cmd']=inspect['Config']['Cmd']+['--speculative-config','{}'];files[name]=json.dumps(inspect).encode()
        result=MODULE.derive_multi_user(files)
        self.assertFalse(result['gates']['launched_multi_user_profile']);self.assertFalse(result['passed'])

    def test_unfrozen_reference_fails(self):
        files=self.build();files['reference/multi-user/short-ladder.json']+=b' '
        self.assertFalse(MODULE.derive_multi_user(files)['gates']['references_are_the_frozen_single_user_answers'])

    def test_incomplete_stage_fails_instead_of_raising(self):
        files=self.build();del files['run/multi-user/session/stop-request.json']
        result=MODULE.derive_multi_user(files)
        self.assertFalse(result['passed']);self.assertIn('stop-request.json',result['error'])

    def test_derive_adds_the_gate_only_with_the_stage(self):
        files=dict(self.packet,**self.build(flip=True))
        result=MODULE.derive(files)
        self.assertIs(result['gates']['multi_user_exact_16_32_64_both_passes'],False)
        self.assertEqual(result['multi_user'],MODULE.derive_multi_user(files));self.assertFalse(result['passed'])

if __name__=='__main__':unittest.main()
