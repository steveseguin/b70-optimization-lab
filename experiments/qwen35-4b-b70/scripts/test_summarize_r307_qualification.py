import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('summary',Path(__file__).with_name('summarize-r307-qualification.py'))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    cases=[{'id':f'L{i}','prompt_ids':[1]*i,'expected_ids':[2]*(256-i),'max_tokens':256-i} for i in range(8,28)]
    rows=[]
    for case in cases:
        for repeat in (-1,0,1):
            rows.append({'case':case['id'],'repeat':repeat,'concurrency':1,'passed':True,'exact':True,
                'token_ids':case['expected_ids'][:], 'usage':{'prompt_tokens':len(case['prompt_ids']),'completion_tokens':case['max_tokens']},
                'cached_tokens':[0], 'finish_reason':'length'})
    return {'status':'complete','passed':True,'mode':'oracle','max_model_len':256,'configuration':{'concurrency':[1],'iters':2},'cases':cases,'rows':rows}


class Tests(unittest.TestCase):
    def test_direct_ids_coverage_and_cache(self):
        good=fixture()
        self.assertTrue(m.boundary(good)['passed'])
        for mutate in [lambda d:d['rows'][0]['token_ids'].__setitem__(0,3),
                       lambda d:d['rows'].pop(),lambda d:d['rows'][0].update(cached_tokens=None),
                       lambda d:d.update(status='running'),lambda d:d['rows'].append(copy.deepcopy(d['rows'][0]))]:
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):m.boundary(bad)

    def test_inventory_requires_all17_matching_files(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'observed',Path(d)/'expected'
            lines=[f'{i:064x}  /file{i}' for i in range(17)]
            a.write_text('\n'.join(lines)+'\n'); b.write_text('\n'.join(reversed(lines))+'\n')
            self.assertTrue(m.check_inventory(a,b)['inventory_equal'])
            a.write_text('\n'.join(lines[:-1])+'\n')
            with self.assertRaises(ValueError):m.check_inventory(a,b)
            lines[0]='f'*64+'  /file0'
            a.write_text('\n'.join(lines)+'\n')
            with self.assertRaises(ValueError):m.check_inventory(a,b)

    def test_reject_nested_output_in_either_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for out in (root/'single',root/'single/nested',root/'failed/nested'):
                with self.assertRaises(ValueError):m.validate_output(root/'single',root/'failed',out)
            m.validate_output(root/'single',root/'failed',root/'out')

    def test_candidate_metadata_is_hash_bound(self):
        with tempfile.TemporaryDirectory() as d:
            inventory=Path(d)/'contract'; inventory.write_text('candidate runtime hashes')
            image='sha256:'+'a'*64
            start={'image':image,'candidate':'r308','inventory_sha256':m.sha(inventory)}
            m.campaign_identity(start,image,'r308',inventory)
            for key,value in [('image',m.IMAGE),('candidate','r307'),('inventory_sha256','0'*64)]:
                bad=dict(start);bad[key]=value
                with self.assertRaises(ValueError):m.campaign_identity(bad,image,'r308',inventory)
            with self.assertRaises(ValueError):m.candidate_identity('latest','r308')
            with self.assertRaises(ValueError):m.candidate_identity(image,'../r308')

    def test_contract_receipt_must_name_same_candidate_image(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'stage';folder.mkdir()
            image='sha256:'+'a'*64
            cap=m.Capture(root/'out',image)
            for line in ['IMAGE CONTRACT PASS: '+m.IMAGE,'IMAGE CONTRACT SKIPPED: '+image]:
                (folder/'server.log').write_text(line)
                with self.assertRaises(ValueError):cap.contract(folder,root,'single')
            (folder/'server.log').write_text('IMAGE CONTRACT PASS: '+image)
            self.assertIn(image,cap.contract(folder,root,'single')['lines'][0])

    def test_explicit_rebuild_root_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaises(ValueError):
                m.analyze(root/'single',root/'failed',root/'rebuild/out',rebuild_root=root/'rebuild')

    def test_incomplete_campaign_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            summary=m.analyze(root/'single',root/'failed',root/'out')
            self.assertFalse(summary['passed'])
            self.assertIn('missing DONE',summary['error'])
            self.assertFalse((root/'single').exists())
            self.assertTrue((root/'out/summary.json').exists())


if __name__=='__main__':unittest.main()
