"""Mutation gates for real chain links and teardown/closure admission; CPU only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import packet58_submission as S
import suite_driver as D
import window as W

class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.chain=self.root/'evidence/chain';self.chain.mkdir(parents=True)
        self.patch=patch.object(S,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.order=('K1a','K1b',*D.WINDOWS)
        for i,name in enumerate(self.order):
            directory=self.chain/name;(directory/'run').mkdir(parents=True)
            (directory/'run/k1.json').write_text('{"passed":true}')
            self.save(directory/'window.json',dict(started_utc_ns=10+i*10,finished_utc_ns=15+i*10))
    def save(self,path,row):path.write_text(json.dumps(row))
    def refs(self,name):
        i=self.order.index(name)
        return dict(started_utc_ns=10+i*10,finished_utc_ns=15+i*10,
            previous=S.reference(self.chain/self.order[i-1]/'window.json'),
            k1_refs=[dict(S.reference(self.chain/n/'window.json'),native_k1_sha256=S.sha(self.chain/n/'run/k1.json')) for n in ('K1a','K1b')])
    def test_exact_predecessors_for_every_model_stage(self):
        for name in D.WINDOWS:
            self.assertEqual(S.chain_links(self.chain,name,self.refs(name)),[(self.chain/n/'window.json').resolve() for n in ('K1a','K1b')])
    def test_previous_sibling_with_identical_bytes_rejected(self):
        sibling=self.root/'sibling.json';sibling.write_bytes((self.chain/'KD/window.json').read_bytes())
        row=self.refs('W2m');row['previous']=S.reference(sibling)
        with self.assertRaisesRegex(ValueError,'immediate chain'):S.chain_links(self.chain,'W2m',row)
    def test_previous_omission_or_tamper_rejected(self):
        row=self.refs('W2m');row.pop('previous')
        with self.assertRaises(KeyError):S.chain_links(self.chain,'W2m',row)
        row=self.refs('W2m');row['previous']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'evidence changed'):S.chain_links(self.chain,'W2m',row)
    def test_arbitrary_k1_pair_rejected(self):
        row=self.refs('KD');sibling=self.root/'k1-other.json';sibling.write_bytes((self.chain/'K1a/window.json').read_bytes())
        row['k1_refs'][0]=dict(S.reference(sibling),native_k1_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'this chain'):S.chain_links(self.chain,'KD',row)
    def test_unbound_k1_native_change_rejected(self):
        row=self.refs('KD');(self.chain/'K1a/run/k1.json').write_text('{"passed":false}')
        with self.assertRaisesRegex(ValueError,'native reference changed'):S.chain_links(self.chain,'KD',row)
    def test_k1_order_and_missing_second_rejected(self):
        for mutate in (lambda r:r['k1_refs'].reverse(),lambda r:r['k1_refs'].pop()):
            row=self.refs('KD');mutate(row)
            with self.assertRaises(ValueError):S.chain_links(self.chain,'KD',row)
    def test_overlap_and_malformed_time_rejected(self):
        for start,end in ((24,35),(True,35),('30',35),(35,30)):
            row=self.refs('KD');row.update(started_utc_ns=start,finished_utc_ns=end)
            with self.assertRaises(ValueError):S.chain_links(self.chain,'KD',row)
    def test_prerequisite_cannot_omit_k1_native_json(self):
        directory=self.chain/'K1a';identity=dict(boot_id='boot',build_receipt_sha256='seal',artifacts_sha256={},environment={},card=0,context=4096,gpu_count=1)
        names=('run/k1.json','run/k1-cases.jsonl','summary.json','kernel-before.jsonl','kernel-window.jsonl')
        for leaf in names:
            path=directory/leaf
            if not path.exists():path.write_text('')
        row=dict(identity,schema='own-runtime.packet58.window.v1',window='K1',passed=True,qualifying=False,
            device_executed=True,child_still_running=False,stop_reasons=[],pid=10,process_start_ticks=20,
            native_files={leaf:W.sha(directory/leaf) for leaf in names})
        self.save(directory/'window.json',row);W.prerequisite(directory/'window.json','K1',identity)
        del row['native_files']['run/k1.json'];self.save(directory/'window.json',row)
        with self.assertRaisesRegex(ValueError,'closure incomplete'):W.prerequisite(directory/'window.json','K1',identity)
    def test_native_summary_requires_drained_single_owner(self):
        out=self.root/'native';(out/'run').mkdir(parents=True)
        owner=dict(safe_to_exit=True,idle_marker_complete=True,exit_code=0,live_bytes=0,in_flight=0)
        base=dict(passed=True,safe_to_exit=True,device_executed=True,owner_cards=1,teardown=[owner])
        manifest={'prompts':[{'prompt_id':'fixture'}]}
        with patch.object(D,'compare_request',return_value={}),patch.object(D.METRICS,'aggregate',return_value={}),patch.object(D,'sha',return_value='a'*64):
            self.save(out/'run/receipt.json',base);self.assertTrue(D.summarize(out,'KD',manifest)['passed'])
            for mutate in (lambda r:r.update(teardown=[]),lambda r:r['teardown'][0].update(in_flight=1),lambda r:r['teardown'][0].update(live_bytes=1024),lambda r:r['teardown'][0].update(exit_code=False),lambda r:r['teardown'][0].update(idle_marker_complete=False)):
                row=copy.deepcopy(base);mutate(row);self.save(out/'run/receipt.json',row)
                with self.assertRaises(ValueError):D.summarize(out,'KD',manifest)

if __name__=='__main__':unittest.main()
