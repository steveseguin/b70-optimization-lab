"""Launch templates use synthetic bytes and never invoke an engine or observer."""
import json
from pathlib import Path
import shutil
from unittest import mock
import unittest

import launch_plan as launch
import prepare as prep
import test_prepare as fixtures


class LaunchPlanTests(unittest.TestCase):
    pin = fixtures.DeploymentTests.pin
    run_prepare = fixtures.DeploymentTests.run_prepare
    # Reuse tiny fixtures without inheriting their separately discovered tests.
    def setUp(self):
        fixtures.DeploymentTests.setUp(self)
        self.run_prepare(draft_root=self.draft,tokenizer_root=self.draft)
        self.binding_sha=prep.digest((self.out/'binding.json').read_bytes())
        self.policy=json.loads((launch.PROFILE/'launch-policy.json').read_text())
        self.policy['model_profile_sha256']=self.sha
        dispatch=b'{"test":"dispatch"}'
        (self.assets/'dispatch-f32-select-gdn2.json').write_bytes(dispatch)
        self.policy['dispatch']['sha256']=prep.digest(dispatch)
        policy_raw=prep.encoded(self.policy)
        (self.assets/'launch-policy.json').write_bytes(policy_raw)
        self.policy_patch=mock.patch.object(launch,'PROFILE',self.assets);self.policy_patch.start();self.addCleanup(self.policy_patch.stop)
        self.sha_patch=mock.patch.object(launch,'POLICY_SHA256',prep.digest(policy_raw));self.sha_patch.start();self.addCleanup(self.sha_patch.stop)
        self.binary=self.root/'fake-engine';self.binary.write_bytes(b'not executable, CPU fixture only')
        self.rope=self.root/'rope.bf16';self.rope.write_bytes(b'fixture')
        self.receipt_path=self.root/'receipt.json'
        self.receipt=dict(schema='ownrt.engine.build.v1',binary=str(self.binary),binary_sha256=prep.digest(self.binary.read_bytes()),
            generated_authority=prep.validate_overlay(self.out/'include',self.sha,self.binding_sha),
            generated_dependencies={str(self.out/'include'/prep.HEADER):prep.digest((self.out/'include'/prep.HEADER).read_bytes())},
            runtime_assets={str(self.rope):prep.digest(self.rope.read_bytes())})
        self.receipt_path.write_bytes(prep.encoded(self.receipt))
        self.lib=self.root/'runtime-libs';self.lib.mkdir()
        self.run=self.root/'run'

    def generate(self, mode='target-only', count=2, max_new=32, **policy):
        return launch.make_plan(self.out,self.sha,self.binding_sha,self.receipt_path,prep.digest(self.receipt_path.read_bytes()),
            ['0000:23:00.0','0000:47:00.0','0000:27:00.0','0000:43:00.0'][:count],
            [self.lib],self.run,[1,2,3],mode,max_new=max_new,**policy)

    def external_policy(self, **changes):
        folder=self.root/'selected-tuning';folder.mkdir()
        policy=dict(self.policy,**changes)
        shutil.copyfile(self.assets/'dispatch-f32-select-gdn2.json',folder/'dispatch-f32-select-gdn2.json')
        path=folder/'policy.json';path.write_bytes(prep.encoded(policy))
        return dict(policy_path=path,policy_sha256=prep.digest(path.read_bytes()))

    def test_explicit_policy_relocates_without_compiled_profile_directory(self):
        default=self.generate()
        selected=self.external_policy(boundaries={'2':[0,24,48],'4':[0,12,24,36,48]})
        with mock.patch.object(launch,'PROFILE',self.root/'absent-builtin'):
            result=self.generate(**selected)
        self.assertEqual(result['boundaries'],[0,24,48])
        self.assertEqual(result['launch_policy'],dict(path=str(selected['policy_path']),sha256=selected['policy_sha256']))
        self.assertEqual(result['pins'][str(selected['policy_path'])],selected['policy_sha256'])
        self.assertEqual(default['stages'][0]['environment'],result['stages'][0]['environment'])
        self.assertIn(str(selected['policy_path'].parent/'dispatch-f32-select-gdn2.json'),result['stages'][0]['argv'])
        legacy=self.generate('mtp',**selected)
        self.assertEqual(legacy['boundaries'],[0,24,48])
        for stage in legacy['stages']:
            self.assertEqual(stage['argv'][stage['argv'].index('--target-split')+1],'24')
        self.assertFalse(self.run.exists())

    def test_policy_needs_separate_trust_and_model_binding(self):
        selected=self.external_policy(model_profile_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'another model'):self.generate(**selected)
        for kwargs in ({'policy_path':selected['policy_path']},{'policy_sha256':selected['policy_sha256']}):
            with self.assertRaisesRegex(ValueError,'supplied together'):self.generate(**kwargs)
        selected['policy_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'pinned artifact'):self.generate(**selected)

    def test_policy_selection_does_not_expand_capabilities_or_escape_dispatch(self):
        selected=self.external_policy()
        for changes in ({'schema':'ownrt.unknown.v1'},{'context':8192},
                        {'boundaries':{'2':[0,48,23],'4':[0,13,25,37,48]}},
                        {'dispatch':dict(file='../outside.json',sha256='a'*64)},
                        {'environment':dict(self.policy['environment'],FilterBdfPath='0000:00:00.0')},
                        {'environment':dict(self.policy['environment'],LD_PRELOAD='bad.so')},
                        {'target_flags':self.policy['target_flags']+['--pipeline-stage','1']},
                        {'mtp':dict(draft_rank=1,experts='fp8',prefill_rows=0)},
                        {'eos_token_ids':[True]}):
            selected['policy_path'].write_bytes(prep.encoded(dict(self.policy,**changes)))
            selected['policy_sha256']=prep.digest(selected['policy_path'].read_bytes())
            with self.assertRaises(ValueError):self.generate(**selected)

    def test_two_four_stage_templates_match_protocol_and_local_binding(self):
        for count in (2,4):
            result=self.generate(count=count)
            self.assertFalse(result['run_authorized']);self.assertFalse(result['device_execution_requested'])
            self.assertFalse(result['portable_observer_available']);self.assertFalse(self.run.exists())
            self.assertEqual(len(result['stages']),count)
            self.assertEqual(result['process_requirements']['nice'],19)
            self.assertEqual(result['process_requirements']['io_priority_class'],3)
            self.assertTrue(result['process_requirements']['controller_must_check_before_spawn'])
            for i,stage in enumerate(result['stages']):
                argv=stage['argv'];self.assertEqual(argv[argv.index('--pipeline-stage')+1],str(i))
                self.assertEqual(argv[:3],['/usr/bin/ionice','-c','3'])
                self.assertEqual(argv[argv.index('--identity')+1],str(self.out/'shard-auth.tsv'))
                self.assertEqual(argv[argv.index('--output')+1],str(self.run/f'stage{i}/native'))
                self.assertNotIn('--draft-mtp',argv)
                self.assertNotIn('HOME',stage['environment'])
            self.assertNotIn('observer',result)
            self.assertNotIn('adapter',json.dumps(result).lower())

    def test_legacy_mtp_uses_shared_pair_and_existing_authenticated_draft(self):
        result=self.generate('mtp')
        self.assertEqual(result['protocol'],'legacy-native-two-rank-mtp')
        first,second=result['stages']
        self.assertEqual(first['shared'],second['shared'])
        self.assertIn('--draft-mtp',first['argv']);self.assertNotIn('--draft-mtp',second['argv'])
        self.assertIn(str(self.out/'draft-manifest.tsv'),first['argv'])
        self.assertNotIn('--pipeline-stage',first['argv'])
        self.assertEqual(result['prefill_rows'],0)
        with self.assertRaisesRegex(ValueError,'two ranks'):self.generate('mtp',4)

    def test_legacy_mtp_cap_remains_128_while_pipeline_templates_allow_512(self):
        self.assertEqual(self.generate('mtp',max_new=128)['max_new'],128)
        with self.assertRaisesRegex(ValueError,'legacy MTP native output cap'):
            self.generate('mtp',max_new=129)
        self.assertEqual(self.generate('target-only',max_new=512)['max_new'],512)

    def test_hash_and_binding_changes_prevent_planning(self):
        self.binary.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'binary changed'):self.generate()
        self.binary.write_bytes(b'not executable, CPU fixture only')
        with (self.model/'a.gguf').open('ab') as stream:stream.write(b'X')
        with self.assertRaisesRegex(ValueError,'local model identity changed'):self.generate()

    def test_lab_environment_not_inherited(self):
        with mock.patch.dict(launch.os.environ,{'OWNRT_GSQ_FUSE_NORM':'1','OWNRT_DECODE_PROFILE':'2','LD_PRELOAD':'poison'}):
            result=self.generate()
        for stage in result['stages']:
            self.assertNotIn('OWNRT_GSQ_FUSE_NORM',stage['environment'])
            self.assertNotIn('OWNRT_DECODE_PROFILE',stage['environment'])
            self.assertNotIn('LD_PRELOAD',stage['environment'])

    def test_changed_rope_dispatch_and_bad_bdf_refused(self):
        self.rope.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'RoPE'):self.generate()
        self.rope.write_bytes(b'fixture')
        (self.assets/'dispatch-f32-select-gdn2.json').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'dispatch'):self.generate()



if __name__=='__main__':unittest.main()
