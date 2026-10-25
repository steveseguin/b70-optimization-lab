from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import driver_proposal as driver


class DriverTests(unittest.TestCase):
    def fixture(self, folder):
        manifest=folder/'draft-manifest.json';manifest.write_text('{"authorized":"fixture"}')
        adapter=folder/'adapter.json'
        adapter.write_text(json.dumps(dict(rank_argv=[['--draft-mtp','--draft-fault','none',
            '--draft-manifest',str(manifest),'--draft-model','/fixture/model','--draft-experts','fp8']])))
        sources={'pipeline/ring/'+n+'.hpp' for n in ('stage_ring','wire','checkpoint_ring','engine_backend','dispatcher')}
        sources|={'pipeline/recursive_provider/'+n for n in ('batch.hpp','draft_runtime_extension.inc',
            'final_event.hpp','peer.hpp','admission.hpp','pending_survival.inc','survival_identity.hpp','survival_writer.inc')}
        sources|={'pipeline/live_draft.hpp','pipeline/operator_state.hpp'}
        receipt=folder/'receipt.json';receipt.write_text(json.dumps({'sources':dict.fromkeys(sources,'fixture')}))
        config=dict(rolling_depth2_prototype=True,use_proposals=True,verify_recursive_restore=True,
            verify_restore=True,verify_provider_survival=True,eos_token_ids=[96,95],
            trusted_draft_manifest_sha256=sha256(manifest.read_bytes()).hexdigest(),
            adapter_plan=str(adapter),build_receipt=str(receipt))
        path=folder/'config.json';path.write_text(json.dumps(config))
        def baseline(_):return dict(config=str(path),output=str(folder/'output'),pins={},prompt_tokens=[3,5,8,11],
            model_identity_sha256='a'*64,context=128,vocab=97,max_new=32,eos=96,
            stages=[dict(id=i,first=i==0,final=i==3,argv=['--draft-rank','0'],
                environment={'OWNRT_DRAFT_DEPTH_PROBE':'0','OWNRT_DRAFT_DEPTH_VERIFY':'0'}) for i in range(4)])
        return path,config,manifest,baseline

    def test_planner_identity_capabilities_all_verification_and_no_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,manifest,baseline=self.fixture(Path(tmp))
            with patch.object(driver.base,'make_plan',side_effect=baseline):plan=driver.make_plan(path)
            self.assertEqual(plan['draft_model_sha256'],config['trusted_draft_manifest_sha256'])
            self.assertEqual(plan['config_sha256'],driver.base.digest(path))
            self.assertNotIn('recursive_reference',plan)
            self.assertIn(str(manifest),plan['pins'])
            self.assertTrue(any(p.endswith('/socket_bridge.py') for p in plan['pins']))
            for stage in plan['stages']:
                self.assertIn('--pipeline-ring-pending-provider',stage['argv'])
                self.assertIn('--pipeline-ring-verify-restore',stage['argv'])
                self.assertEqual('--pipeline-ring-verify-provider-survival' in stage['argv'],stage['first'])
                self.assertEqual('--pipeline-ring-recursive-verify-restore' in stage['argv'],stage['first'])
                self.assertNotIn('OWNRT_DRAFT_DEPTH_PROBE',stage['environment'])
            config['eos_token_ids']=[96];path.write_text(json.dumps(config))
            with patch.object(driver.base,'make_plan',side_effect=baseline):changed=driver.make_plan(path)
            self.assertNotEqual(plan['request_sha256'],changed['request_sha256'])

    def test_wrong_valid_manifest_and_missing_native_writer_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,manifest,baseline=self.fixture(Path(tmp))
            manifest.write_text('{"authorized":"different"}')
            with patch.object(driver.base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'trusted SHA'):
                driver.make_plan(path)
            manifest.write_text('{"authorized":"fixture"}')
            receipt=Path(config['build_receipt']);data=json.loads(receipt.read_text())
            del data['sources']['pipeline/recursive_provider/survival_writer.inc'];receipt.write_text(json.dumps(data))
            with patch.object(driver.base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'capability'):
                driver.make_plan(path)

    def test_reference_or_disabled_verification_refused_before_base_planner(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,_,_=self.fixture(Path(tmp))
            for extra in ({'recursive_reference':'/unused'}, {'verify_provider_survival':False},
                          {'scripted_proposal_tokens':[]}, {'pending_cases':[]}):
                path.write_text(json.dumps(dict(config,**extra)))
                with patch.object(driver.base,'make_plan') as planner,self.assertRaises(ValueError):
                    driver.make_plan(path)
                planner.assert_not_called()

    def test_existing_guarded_lifecycle_injected_without_new_process_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan=dict(output=tmp)
            with patch.object(driver.live.target.lifecycle,'execute') as execute:
                driver.execute(plan,{'admission':'fixture'},'fixture-unit')
            self.assertIs(execute.call_args.kwargs['stage_type'],driver.bridge.Stage)
            self.assertIs(execute.call_args.kwargs['driver'],driver.bridge.drive)
            self.assertIs(execute.call_args.kwargs['scripted_proposals'],False)


if __name__ == '__main__':unittest.main()
