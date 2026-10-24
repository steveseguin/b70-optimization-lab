"""Offline source/ELF closure checks only; never invokes any executable."""
import hashlib
import json
from pathlib import Path
import re
import unittest

P=Path(__file__).resolve().parents[1]
ROOT=P.parents[3]
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class NativeCompileAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preparation=read(P/'evidence/build-preparation.json')
        cls.build=read(P/'evidence/build-compile-only.json')
        cls.main=(P/'build/native/main.cpp').read_text()
        cls.runtime=(P/'production_runtime.hpp').read_text()

    def test_historical_preparation_preserved_and_final_closure_current(self):
        old=self.preparation
        self.assertTrue(old['passed'] and old['prepared_only'])
        self.assertFalse(old['compiled'])
        for path,want in old['artifact_sha256'].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in old['source_sha256'].items():
            copies=[name for name,digest in old['artifact_sha256'].items() if Path(name).name==Path(path).name and digest==want]
            self.assertEqual(len(copies),1,path)
        self.assertTrue(self.build['passed'] and self.build['compile_only'] and self.build['public_entry_disabled'])
        for key in ('fixture_executed','device_enumerated','device_executed','model_executed'):
            self.assertFalse(self.build[key])
        for group in ('artifact_sha256','source_sha256'):
            for path,want in self.build[group].items():self.assertEqual(sha(ROOT/path),want,path)
        overlay=self.build['generated']
        for group in ('parent_source_sha256','source_sha256'):
            for path,want in overlay[group].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in overlay['outputs'].items():self.assertEqual(sha(P/path),want,path)

    def test_native_compile_reuses_exact_parent_arithmetic_objects(self):
        item=self.build['plan']
        parent=read(P.parent/'packet198-postreply-checkpoint/evidence/build-compile-only.json')
        prior=next(x for x in parent['plans'] if x['target']=='device')
        removed={path for path in prior['objects'] if any(name in Path(path).name for name in
                 ('own-rt-iq3-entry','entry-nongemv_fixture','entry-k2_fixture'))}
        self.assertEqual(item['objects'],{path:digest for path,digest in prior['objects'].items() if path not in removed})
        for path,want in item['objects'].items():self.assertEqual(sha(path),want,path)
        compile,link=item['commands']
        self.assertIn('-fsycl',compile);self.assertNotIn('-DOWN_RT_HOST_ONLY',compile)
        for flag in ('-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee'):
            self.assertIn(flag,compile);self.assertIn(flag,link)
        self.assertEqual(set(x for x in link if x.endswith('.o')),set(item['objects'])|{item['object']})
        self.assertEqual(compile[compile.index('-c')+1],str(P/'build/native/entry-main.cpp'))
        self.assertEqual(compile[compile.index('-o')+1],item['object'])
        self.assertEqual(link[link.index('-o')+1],item['binary'])
        self.assertEqual(sha(item['binary']),item['binary_sha256'])
        self.assertEqual(sha(item['object']),item['object_sha256'])
        for path,want in item['repository_dependencies'].items():self.assertEqual(sha(ROOT/path),want,path)
        for local in ('production_schedule.hpp','production_runtime.hpp','cache_interval.hpp','build/native/main.cpp'):
            self.assertIn(str((P/local).relative_to(ROOT)),item['repository_dependencies'])
        blob=Path(item['binary']).read_bytes()
        self.assertEqual(blob[:6],b'\x7fELF\x02\x01')

    def test_public_entry_disabled_in_source_and_offline_disassembly(self):
        entry=(P/'build/native/entry-main.cpp').read_text()
        self.assertIn('#define main p212_model_body',entry)
        self.assertIn('extern "C" int p212_future_entry',entry)
        public=entry[entry.index('int main(int,char**)'):]
        self.assertIn('return 64;',public)
        self.assertNotIn('p212_model_body(',public)
        self.assertNotIn('p212_future_entry(',public)
        self.assertTrue(self.build['generated']['entry_disabled'])
        self.assertFalse(self.build['generated']['native_execution_allowed'])
        paths=[ROOT/path for path in self.build['artifact_sha256'] if 'main' in Path(path).name and Path(path).suffix=='.log']
        self.assertEqual(len(paths),1,'exact offline public-main disassembly log')
        assembly=paths[0].read_text()
        self.assertRegex(assembly,r'<main>:')
        self.assertRegex(assembly,r'\$0x40,%eax')
        self.assertNotIn('p212_future_entry',assembly)
        self.assertNotIn('p212_model_body',assembly)

    def test_production_gate_and_shared_runtime_selector_source(self):
        gate=self.main[self.main.index('static void p212_options'):self.main.index('static Options parse')]
        for token in ('a.p212_prefill','!a.mini','!a.pipeline_mini','!a.mtp','a.cards==1','a.rank==-1',
                      'a.context==4096','a.memory=="resident"','a.miss_path=="zero-copy"','a.cache_maintenance=="serial"',
                      'a.cache_cap=="max"','a.cache_bytes==21552729600ull','a.hc=="p60fusion"',
                      'a.hc_geometry=="hc-wide"','a.experts=="wide64+halfcache"','a.other_fusion=="fused"',
                      'a.retirement=="ordered-foreground"','a.retain_steps.ranges.empty()'):
            self.assertIn(token,gate)
        self.assertIn('p212_options(a);',self.main)
        self.assertIn('schedule=build_schedule(sites,tensors);steps=ordered_steps(schedule);',self.runtime)
        self.assertIn('for(size_t cursor=0;cursor<steps.size();)',self.runtime)
        self.assertIn('e.enqueue(e.p.launches.at(steps[cursor].index),e.logical)',self.runtime)
        self.assertIn('e.gemv_choices.at(&l).first=="p33.dense.segment"',self.runtime)
        self.assertIn('need(l.card==0',self.runtime)
        self.assertIn('p208::paired_projection',self.runtime)
        self.assertIn('pair.commands[0].ids.size()==7',self.runtime)
        schedule=read(P/'evidence/schedule-build.json')
        key=str((P/'production_schedule.hpp').relative_to(ROOT))
        self.assertEqual(self.build['plan']['repository_dependencies'][key],schedule['repository_dependencies'][key])
        # These are reviewed source drift guards, not executed model/GPU claims.
        self.assertIn('p58ag::expert(dev(c),selected,b,halfcache,a.experts=="wide64+halfcache")',self.main)
        self.assertIn('p49d::expert(dev(c),selected,kind,b,sealed_selection.choices.at("down"))',self.main)

    def test_offline_pair_images_and_backend_lineage(self):
        image=self.build['offline_image'];item=self.build['plan']
        self.assertTrue(image['linked_qualification_symbol'] and image['linked_sycl_registration'])
        self.assertTrue(any(x.startswith('sycl-spir64') for x in image['targets']))
        expected={'_ZTSN4p20816NativePairKernelILj10240EEE','_ZTSN4p20816NativePairKernelILj6144EEE'}
        self.assertTrue(expected<=set(image['kernel_entries']))
        bitcode=P/'build/native/pair-device.bc'
        self.assertEqual(sha(bitcode),image['bitcode_sha256'])
        self.assertEqual(bitcode.stat().st_size,image['bitcode_bytes'])
        for path,want in image['symbol_files'].items():self.assertEqual(sha(ROOT/path),want,path)
        provenance=self.build['backend_provenance']
        self.assertEqual(sha(ROOT/provenance['source']),provenance['source_sha256'])
        self.assertEqual(sha(ROOT/provenance['object']),provenance['object_sha256'])
        self.assertEqual(item['objects'][str(ROOT/provenance['object'])],provenance['object_sha256'])
        self.assertIn('not executed',provenance['ordering_scope'])
        lineage=P.parent/'packet181-session-swap-v3/one-card/lineage'
        self.assertEqual(sha(lineage/'build-receipt.json'),provenance['lineage_receipt_sha256'])
        self.assertEqual(sha(lineage/'build-inputs.json'),provenance['copy_inputs_sha256'])

if __name__=='__main__':unittest.main()
