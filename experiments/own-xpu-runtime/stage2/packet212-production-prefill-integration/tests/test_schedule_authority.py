"""Read-only source and retained pure-scheduler evidence; no process starts."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]
ROOT=P.parents[3]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

class ScheduleAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=read(P/'schedule-inputs.json')
        cls.build=read(P/'evidence/schedule-build.json')
        cls.proof=read(P/'evidence/schedule-proof.json')
        cls.sites=cls.inputs['sites'];cls.events=cls.proof['events']

    def test_exact_retained_sources_and_repeatable_extraction(self):
        for name,want in self.inputs['source_sha256'].items():
            self.assertEqual(sha(ROOT/name),want,name)
        spec=importlib.util.spec_from_file_location('p212_source_metadata',P/'prepare_fixture.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.extract(),self.inputs)
        self.assertEqual((len(self.sites),self.inputs['prepared_command_rows'],self.inputs['distinct_prepared_sites'],self.inputs['logical_sites_without_prepared_commands']), (1486,1118,1016,470))

    def test_pure_cpu_build_and_exact_header(self):
        self.assertTrue(self.build['passed'])
        self.assertFalse(self.build['runtime_executed'] or self.build['device_executed'] or self.build['model_executed'])
        for name,want in self.build['source_sha256'].items():self.assertEqual(sha(ROOT/name),want,name)
        expected={str((P/name).relative_to(ROOT)) for name in ('production_schedule.hpp','schedule_fixture.cpp')}
        self.assertEqual(set(self.build['repository_dependencies']),expected)
        for name,want in self.build['repository_dependencies'].items():self.assertEqual(sha(ROOT/name),want,name)
        self.assertEqual(self.build['compile_command'][0],'/usr/bin/g++')
        self.assertFalse(any(arg.endswith('.o') for arg in self.build['compile_command']))
        self.assertEqual(sha(self.build['binary']),self.build['binary_sha256'])
        self.assertEqual(sha(P/'evidence/schedule-proof.json'),self.build['proof_sha256'])
        self.assertEqual(read(Path(self.build['attempt'])/'stdout.json'),self.proof)
        self.assertTrue(self.proof['passed'])
        self.assertFalse(self.proof['runtime_executed'] or self.proof['device_executed'] or self.proof['model_executed'])

    def test_full_original_row_chains_and_final_exclusion(self):
        nonfinal=[x['index'] for x in self.sites if x['label'].startswith('blk.') or x['label'] in ('begin.0','embedding','streams')]
        self.assertEqual(len(nonfinal),1479)
        rowchains=[[],[]];coverage=Counter();pair_indices=[]
        for event in self.events:
            index=event['site'];self.assertEqual(self.sites[index]['card'],0)
            if event['kind']=='pair':
                self.assertEqual(event['row'],-1);rows=(0,1);pair_indices.append(index)
            else:self.assertEqual(event['kind'],'m1');self.assertIn(event['row'],(0,1));rows=(event['row'],)
            for row in rows:rowchains[row].append(index);coverage[index]+=1
        self.assertEqual(rowchains,[nonfinal,nonfinal])
        self.assertEqual(coverage,Counter({i:2 for i in nonfinal}))
        self.assertEqual(len(pair_indices),70)
        self.assertEqual(len(self.events),2888)
        self.assertEqual(self.proof['m1_site_invocations'],2818)
        for index in pair_indices:
            site=self.sites[index];projection=site['projection']
            self.assertTrue(site['label'].endswith(('.gdn.qkv','.gdn.z')))
            self.assertNotEqual(int(site['label'].split('.')[1]),2)
            self.assertEqual((projection['type_code'],projection['variant'],projection['columns']), (14,6,2560))
            self.assertEqual(projection['stored_bytes'],projection['rows']*3380)
        self.assertEqual([x['label'] for x in self.sites if x['index'] not in coverage],
                         ['final.norm','final.low','final.gate','final.mix','logits','argmax','commit.final'])

    def test_actual_capture_multiplicity_and_empty_followers(self):
        commands=empty=0
        for event in self.events:
            count=self.sites[event['site']]['recorded_prepared_commands']
            if event['kind']=='pair':self.assertEqual(count,1)
            else:commands+=count;empty+=count==0
        self.assertEqual(commands,self.proof['recorded_m1_commands'])
        self.assertEqual(empty,self.proof['empty_site_invocations'])
        self.assertGreater(empty,0)
        prepared=next(ROOT/x for x in self.inputs['source_sha256'] if x.endswith('prepared-arguments-parity0.jsonl'))
        observed=Counter(json.loads(line)['site'] for line in prepared.read_text().splitlines())
        self.assertEqual([observed[i] for i in range(1486)], [x['recorded_prepared_commands'] for x in self.sites])

    def test_qsa_ple_and_q8_fallback_causal_order(self):
        for layer in [2,*range(3,48,4)]:
            positions={row:[] for row in (0,1)}
            for n,event in enumerate(self.events):
                if self.sites[event['site']]['label'].startswith(f'blk.{layer}.'):
                    self.assertEqual(event['kind'],'m1');positions[event['row']].append(n)
            self.assertTrue(positions[0] and positions[1]);self.assertLess(max(positions[0]),min(positions[1]))
        q8=[x['projection'] for x in self.sites if x['label'] in ('blk.2.gdn.qkv','blk.2.gdn.z')]
        self.assertEqual([x['type_code'] for x in q8],[8,8]);self.assertEqual([x['stored_bytes'] for x in q8],[31129600,18677760])
        ple=next(x for x in self.sites if x['label']=='blk.1.ple.lookup')
        self.assertEqual(ple['recorded_prepared_commands'],0)
        self.assertEqual(sum(e['site']==ple['index'] for e in self.events),2)

    def test_chronological_routes_and_all_refusals(self):
        expected=[]
        for row in range(2):
            for layer in range(48):
                for slot in range(10):
                    local=(row*23+layer*31+slot*7)%512
                    if row==layer==slot==0:local=511
                    expected.append(layer*512+local)
        self.assertEqual(self.proof['chronological_routes'],expected)
        required={'cross32_refused','final_token_consumption_refused','decode_position_refused','past_capacity_refused',
                  'oversize_input_refused','wrong_context_refused','incomplete_route_log_refused','expert512_refused',
                  'row2_slot_refused','layer48_slot_refused','q6_wrong_stride_refused','q6_wrong_variant_refused',
                  'q6_wrong_columns_refused','q8_cannot_silently_pair','duplicate_site_refused','index_drift_refused',
                  'missing_final_refused','block_order_refused','q8_wrong_layout_refused','mismatched_projection_types_refused',
                  'missing_qkv_refused','missing_z_refused','missing_layer_refused','final_interleaving_refused','wrong_row_order_discriminates'}
        self.assertTrue(required <= set(self.proof['checks']))
        self.assertEqual(len(self.proof['checks']),97)
        self.assertTrue(all(x is True for x in self.proof['checks'].values()))

    def test_initial_helper_failure_preserved_before_compiler(self):
        prior=P/'evidence/schedule-1792802260460381803'
        receipt=read(prior/'receipt.json');summary=read(prior/'failure-summary.json')
        self.assertFalse(receipt['passed'] or summary['compiler_executed'] or summary['fixture_executed'])
        self.assertNotIn('compile_returncode',receipt)
        self.assertIn('ModuleNotFoundError',receipt['error'])
        for name,want in receipt['source_sha256'].items():self.assertEqual(sha(prior/Path(name).name),want)

if __name__=='__main__':unittest.main()
