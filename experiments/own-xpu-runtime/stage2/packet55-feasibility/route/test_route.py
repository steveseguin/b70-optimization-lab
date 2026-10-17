#!/usr/bin/env python3
"""Small CPU tests for binary format, overlay coverage and fail-closed conversion."""
import importlib.util,json,struct,tempfile,unittest
from pathlib import Path
import build,convert

class RouteTests(unittest.TestCase):
    def test_all_overlay_anchors(self):
        original=build.BASE/'build/checked'/build.BASE.relative_to(build.ROOT)
        for name in ('main.cpp','mtp.hpp','rank.hpp','single_device.cpp'):
            before=(original/name).read_text();after=build.overlay(name,before)
            self.assertNotEqual(before,after)
        main=build.overlay('main.cpp',(original/'main.cpp').read_text())
        self.assertIn('a.tokens <= 256',main)
        self.assertEqual(main.count('p55_target_route(p.launches[index])'),1)
        self.assertEqual(main.count('p55_target_route(l);'),1)
        self.assertIn('++engine->p55_command;',build.overlay('rank.hpp',(original/'rank.hpp').read_text()))
    def test_binary_roundtrip_phase_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'routes.bin'
            rows=[(1,10,2,23,0,10,99,1,0),(2,12,2,23,0,10,100,0,0),(3,13,1,0,1,10,101,0,0)]
            file.write_bytes(convert.MAGIC+b''.join(convert.RECORD.pack(*r,*range(10),*([.1]*10)) for r in rows))
            prompt=dict(prompt_id='p',split='test',category='code',prompt_tokens=3)
            result=list(convert.read_records(file,1,prompt))
            self.assertEqual(len(result),3);self.assertTrue(result[0]['speculative']);self.assertFalse(result[1]['speculative'])
            self.assertEqual([r['phase'] for r in result],['decode']*3)
            self.assertEqual(result[0]['position'],result[1]['position'])
            file.write_bytes(file.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'truncated'):list(convert.read_records(file,1,prompt))
    def test_reject_wrong_owner(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'r';file.write_bytes(convert.MAGIC+convert.RECORD.pack(0,1,0,23,0,10,0,0,0,*range(10),*([.1]*10)))
            with self.assertRaisesRegex(ValueError,'owner'):list(convert.read_records(file,0,dict(prompt_id='p',split='test',category='code',prompt_tokens=1)))
    def test_prompts_balanced(self):
        manifest=json.loads((build.P/'calibration-prompts.json').read_text());prompts=manifest['prompts']
        self.assertEqual(len(prompts),24);self.assertEqual(len({x['text'] for x in prompts}),24)
        for split in ('train','test'):
            rows=[x for x in prompts if x['split']==split]
            self.assertEqual(len(rows),12)
            self.assertEqual({c:sum(x['category']==c for x in rows) for c in {x['category'] for x in rows}},dict.fromkeys(('code','prose','analysis','structured','multilingual','math'),2))
if __name__=='__main__':unittest.main()
