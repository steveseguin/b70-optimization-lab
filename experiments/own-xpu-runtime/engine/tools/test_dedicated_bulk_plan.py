"""Pure Python planner contract with mocked base planner; no compiled/device admission."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import dedicated_provider_driver as driver

class BulkPlanTests(unittest.TestCase):
    def fixture(self,root):
        prompt=[i%90 for i in range(520)];raw=struct.pack('<520i',*prompt);tokens=root/'prompt.i32';tokens.write_bytes(raw)
        manifest=root/'manifest';manifest.write_bytes(b'pinned real-shaped manifest fixture')
        adapter=root/'adapter.json';adapter.write_text(json.dumps(dict(rank_argv=[['native','--draft-mtp','--draft-fault','none',
            '--draft-head','full','--draft-manifest',str(manifest),'--draft-model','/draft','--draft-experts','fp8']])))
        required={'pipeline/provider_only/'+x:'test-source' for x in ('bootstrap.inc','owner.hpp','runtime.hpp','wire.hpp','peers.hpp','prefill.hpp')}
        receipt=root/'receipt.json';receipt.write_text(json.dumps(dict(sources=required)))
        config=root/'config.json';c=dict(dedicated_provider=True,dedicated_bulk_prefill=True,build_receipt=str(receipt),
            adapter_plan=str(adapter),provider_bdf='0000:43:00.0',eos_token_ids=[96],trusted_draft_manifest_sha256=sha256(manifest.read_bytes()).hexdigest(),
            boundaries=[0,25,48],dedicated_prefill_prompt=str(tokens),dedicated_prefill_prompt_sha256=sha256(raw).hexdigest())
        config.write_text(json.dumps(c))
        out=root/'output'
        stage=lambda i,bdf:dict(id=i,bdf=bdf,first=i==0,final=i==1,begin=0 if i==0 else 25,end=25 if i==0 else 48,
            packed_weight_bytes=1,native_output=str(out/f'stage{i}/native'),argv=['native','--rank',str(i),
            '--shared',str(out/f'stage{i}/shared.bin'),'--output',str(out/f'stage{i}/native'),
            '--pipeline-boundaries','0,25,48','--pipeline-stage',str(i)],environment={})
        plan=dict(stages=[stage(0,'0000:23:00.0'),stage(1,'0000:47:00.0')],model_identity_sha256='model',prompt_tokens=prompt,
            context=1024,max_new=4,vocab=97,eos=96,output=str(out),pins={})
        return config,c,plan,receipt
    def test_real_provider_alias_no_target_map_and_prompt_pins(self):
        with TemporaryDirectory() as td:
            config,c,plan,receipt=self.fixture(Path(td))
            with patch.object(driver.base,'make_plan',side_effect=lambda _:deepcopy(plan)):
                p=driver.make_plan(config)
            self.assertEqual(p['prefill_rows'],256);self.assertTrue(p['dedicated_bulk_prefill'])
            self.assertIn('--provider-prefill-rows',p['provider']['argv'])
            self.assertNotIn('--prefill-rows',p['provider']['argv']);self.assertNotIn('--prefill-shared',p['provider']['argv'])
            for stage in p['stages']:self.assertIn('--prefill-rows',stage['argv'])
            self.assertEqual(p['pins'][c['dedicated_prefill_prompt']],c['dedicated_prefill_prompt_sha256'])
    def test_compiled_capability_and_immutable_prompt_required(self):
        with TemporaryDirectory() as td:
            config,c,plan,receipt=self.fixture(Path(td))
            with patch.object(driver.base,'make_plan',side_effect=lambda _:deepcopy(plan)):
                r=json.loads(receipt.read_text());r['sources'].pop('pipeline/provider_only/prefill.hpp');receipt.write_text(json.dumps(r))
                with self.assertRaisesRegex(ValueError,'capability'):driver.make_plan(config)
                r['sources']['pipeline/provider_only/prefill.hpp']='test-source';receipt.write_text(json.dumps(r))
                Path(c['dedicated_prefill_prompt']).write_bytes(b'wrong')
                with self.assertRaisesRegex(ValueError,'prompt'):driver.make_plan(config)
    def test_overlap_and_reset_explicitly_refused(self):
        with TemporaryDirectory() as td:
            config,c,plan,receipt=self.fixture(Path(td))
            for flag in ('prefill_pipeline','persistent_reset'):
                bad=dict(c,**{flag:True});config.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'sequential'):driver.make_plan(config)

    def test_partial_only_prefix_requires_explicit_suite(self):
        with TemporaryDirectory() as td:
            config,c,plan,receipt=self.fixture(Path(td))
            for count in (2,3,67):
                plan['prompt_tokens']=[i%90 for i in range(count)]
                raw=struct.pack(f'<{count}i',*plan['prompt_tokens'])
                Path(c['dedicated_prefill_prompt']).write_bytes(raw)
                c['dedicated_prefill_prompt_sha256']=sha256(raw).hexdigest()
                for suite in (False,True):
                    cfg=dict(c)
                    if suite:cfg['dedicated_reset_protocol']='ownrt.dedicated-reset-request.v2'
                    config.write_text(json.dumps(cfg))
                    with patch.object(driver.base,'make_plan',side_effect=lambda _:deepcopy(plan)):
                        if suite and count>=3:
                            actual=driver.make_plan(config)
                            self.assertEqual(actual['prompt_tokens'],plan['prompt_tokens'])
                        else:
                            with self.assertRaisesRegex(ValueError,'dedicated prefix'):driver.make_plan(config)

if __name__=='__main__':unittest.main()
