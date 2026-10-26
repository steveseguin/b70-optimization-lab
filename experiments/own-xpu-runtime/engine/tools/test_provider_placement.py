"""Configurable draft owner; exact simulated outputs, cancellation and real sockets."""
import unittest
from test_rolling_provider import fixture,run,reference
from test_rolling_ring_socket import exercise


class ProviderPlacementTests(unittest.TestCase):
    def test_reordered_owners_and_every_cancel_boundary(self):
        for count in (2,4,6):
            for provider in range(count-1):
                for seed in range(8):
                    c,w=fixture(count,provider_stage=provider)
                    run(c,w,random_seed=seed,miss_first=(4,9),miss_second=(6,11))
                    inputs,outputs=reference(list(c.prompt),c.max_new,c.eos)
                    self.assertEqual(c.emitted,outputs)
                    self.assertTrue(all(x.ring.physical['history']==inputs for x in w))
                c,w=fixture(count,maximum=7,provider_stage=provider)
                total=run(c,w,random_seed=6,miss_first=(4,),miss_second=(3,))['ticks']
                for tick in range(total):
                    c,w=fixture(count,maximum=7,provider_stage=provider)
                    run(c,w,random_seed=6,miss_first=(4,),miss_second=(3,),stop_at_tick=tick)
                    self.assertTrue(c.done and not c.provider_jobs)

    def test_fragmented_remote_socket_outputs_and_owned_parent(self):
        observed=set()
        for count in (2,4,6):
            for provider in range(count-1):
                result,states=exercise(count,provider_stage=provider,
                    first_options=dict(capture_ready=True,miss_first=(3,9),miss_second=(6,11),provider_delay=.004),
                    final_options=dict(overwrite_hidden=True))
                inputs,outputs=reference([3,5,8,11],16,(96,))
                self.assertEqual(result['output_ids'],outputs)
                self.assertTrue(all(s['worker'].ring.physical['history']==inputs for s in states))
                observed.update(r['depth'] for r in result['rejected_proposals'])
                self.assertGreater(states[-1].get('overlapped_rows',0),0)
        self.assertEqual(observed,{1,2})

    def test_remote_cancel_and_corrupt_capture(self):
        for count,provider in ((4,2),(6,4)):
            result,_=exercise(count,provider_stage=provider,cancel=True,
                first_options=dict(capture_ready=True,provider_delay=.004))
            self.assertTrue(result['cancelled'])
            for field in ('bad_capture_identity','duplicate_capture','skip_capture'):
                with self.subTest(count=count,field=field),self.assertRaises(ValueError):
                    exercise(count,provider_stage=provider,
                        first_options=dict(capture_ready=True,provider_delay=.001,**{field:True}))

    def test_planner_owner_flags(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        import persistent_rolling_driver as driver
        from test_persistent_rolling import PersistentPlanTests
        for count in (2,4,6):
            for provider in range(count-1):
                with tempfile.TemporaryDirectory() as tmp:
                    path,config,inputs,baseline=PersistentPlanTests().fixture(Path(tmp),'measured')
                    config.update(provider_stage=provider,capture_ready_overlap=True,recursive_flat_copy=True)
                    path.write_text(json.dumps(config))
                    receipt=Path(config['build_receipt']);data=json.loads(receipt.read_text())
                    for name in ('capture_ready.hpp','seed_peer.hpp'):
                        data['sources']['pipeline/recursive_provider/'+name]='fixture'
                    receipt.write_text(json.dumps(data))
                    def base(p):
                        value=baseline(p);sample=value['stages'][0]
                        value['stages']=[dict(sample,id=i,first=i==0,final=i==count-1,
                            argv=list(sample['argv']),environment=dict(sample['environment'])) for i in range(count)]
                        return value
                    with patch.object(driver.base,'make_plan',side_effect=base):plan=driver.make_plan(path)
                    self.assertEqual(plan.get('provider_stage',0),provider)
                    for flag in ('--draft-mtp','--pipeline-ring-recursive-flat-copy','--pipeline-ring-parent-capture-ack'):
                        self.assertEqual([s['argv'].count(flag) for s in plan['stages']],
                            [int(i==provider) for i in range(count)])
                    self.assertEqual([s['argv'].count('--pipeline-ring-seed-shared') for s in plan['stages']],
                        [int(provider>0 and i==provider) for i in range(count)])
                    self.assertEqual([s['argv'].count('--pipeline-provider-stage') for s in plan['stages']],
                        [int(provider>0)]*count)
