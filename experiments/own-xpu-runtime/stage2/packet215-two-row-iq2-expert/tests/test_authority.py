"""Read-only retained IQ2 proof and actual matcher/counter evidence; no owner replay."""
import collections,hashlib,json,struct
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def valid(route):e,start,count=route;return e<512 and start<=640 and count<=640-start
class Authority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.build=read(P/'evidence/cpu-build.json');cls.proof=read(P/'evidence/arithmetic-proof.json');cls.cases={c['name']:c for c in cls.proof['cases']}
    def test_source_objects_compiler_and_original_arithmetic_exact(self):
        b=self.build;self.assertTrue(b['passed']);self.assertFalse(b['device_executed'] or b['native_executed'] or b['model_executed'])
        for group in ('source_sha256','parent_sha256','artifact_sha256'):
            for path,want in b[group].items():self.assertEqual(sha(ROOT/path),want,path)
        plan=b['plan'];self.assertEqual(plan['compile_returncode'],0);self.assertEqual(plan['run_returncode'],0)
        for path,want in plan['repository_dependencies'].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in plan['object_sha256'].items():self.assertEqual(sha(path),want,path)
        self.assertEqual(sha(plan['binary']),plan['binary_sha256']);self.assertEqual(sha(P/'evidence/arithmetic-proof.json'),plan['proof_sha256']);self.assertEqual(sha('/usr/bin/g++'),b['compiler_sha256'])
        relocation=b['selected_header'];source=(ROOT/relocation['source']).read_text();output=(ROOT/relocation['output']).read_text()
        self.assertEqual(source.count(relocation['old_include']),1);self.assertEqual(output,source.replace(relocation['old_include'],relocation['new_include']))
        self.assertEqual(sha(ROOT/relocation['source']),relocation['source_sha256']);self.assertEqual(sha(ROOT/relocation['output']),relocation['output_sha256'])
        self.assertIn('-DOWN_RT_HOST_ONLY',plan['compile_command']);self.assertNotIn('-fsycl',plan['compile_command'])
    def test_all_output_and_status_bytes_bound_to_selected_and_scalar(self):
        self.assertEqual(len(self.cases),17)
        for c in self.cases.values():
            raw=bytes.fromhex(c['output_hex']);flags=bytes.fromhex(c['status_error_hex']);self.assertEqual(len(raw),51200);self.assertEqual(c['bytes'],len(raw));self.assertEqual(len(flags),168)
            digest=hashlib.sha256(raw).hexdigest();self.assertEqual(c['paired_sha256'],digest);self.assertEqual(c['selected_sha256'],digest);self.assertEqual(c['scalar_oracle_sha256'],digest);self.assertEqual(hashlib.sha256(flags).hexdigest(),c['status_error_sha256'])
    def test_every_invalid_or_unwritten_tail_is_exact_bf16_nan(self):
        for name,c in self.cases.items():
            values=struct.unpack('<25600H',bytes.fromhex(c['output_hex']))
            for row in range(2):
                for projection in range(2):
                    for slot,route in enumerate(c['routes'][row]):
                        count=route[2] if valid(route) else 0;offset=(row*2+projection)*6400+slot*640
                        self.assertEqual(set(values[offset+count:offset+640]),{0x7fc0} if count<640 else set(),(name,row,projection,slot))
    def test_exact_route_status_active_and_sticky_error(self):
        for name,c in self.cases.items():
            values=struct.unpack('<42I',bytes.fromhex(c['status_error_hex']))
            for row in range(2):
                flags=[int(not valid(route)) for route in c['routes'][row]];expected_error=c['initial_error'][row]
                if any(flags) and c['active'][row] and not expected_error:expected_error=1
                self.assertEqual(list(values[row*21:(row+1)*21]),flags+flags+[expected_error],(name,row))
    def test_actual_overlap_counter_multisets_and_original_slot_maps(self):
        identity=list(range(10));none=[-1]*10
        expected={'disjoint_full':none,'partial_full':[-1]*5+list(range(5)),'permuted_full':list(reversed(range(10))),'equal_inputs_full_overlap':identity,'permuted_duplicates':[4,9,3,8,2,7,1,6,0,5],'different_halfcache_storage':none}
        for name,slot in [('same_expert_different_slice',3),('same_expert_different_backing',4),('same_expert_different_generation',5)]:expected[name]=identity.copy();expected[name][slot]=-1
        for name in ('invalid_active','invalid_inactive','invalid_sticky_error'):expected[name]=[-1,-1,-1]+list(range(3,10))
        for name,c in self.cases.items():
            self.assertEqual(c['matched_slots'],expected.get(name,identity),name)
            routes=c['routes'];raw=[collections.Counter(r[0] for r in row if r[0]<512) for row in routes];tuples=[collections.Counter(tuple(r) for r in row if valid(r)) for row in routes]
            self.assertEqual(c['raw_id_overlap'],sum((raw[0]&raw[1]).values()),name);self.assertEqual(c['tuple_overlap'],sum((tuples[0]&tuples[1]).values()),name)
            self.assertEqual(c['slot_pairs'],sum(j>=0 for j in c['matched_slots']),name)
            used=[j for j in c['matched_slots'] if j>=0];self.assertEqual(len(used),len(set(used)),name)
        self.assertEqual(self.cases['permuted_duplicates']['slot_pairs'],10) # five distinct IDs, ten slots
    def test_instrumented_decode_savings_and_unchanged_valid_output_count(self):
        for name,c in self.cases.items():
            rows=sum(r[2] for row in c['routes'] for r in row if valid(r));shared=sum(c['routes'][0][i][2] for i,j in enumerate(c['matched_slots']) if j>=0)
            self.assertEqual(c['valid_output_rows'],rows*2,name);self.assertEqual(c['unshared_decoded_tiles'],rows*640,name)
            self.assertEqual(c['shared_decoded_tiles'],shared*640,name);self.assertEqual(c['decoded_tiles'],(rows-shared)*640,name)
            self.assertEqual(c['decoded_tiles']+c['shared_decoded_tiles'],c['unshared_decoded_tiles'],name)
        full=self.cases['equal_inputs_full_overlap'];self.assertEqual(full['decoded_tiles']*2,full['unshared_decoded_tiles'])
        zero=self.cases['valid_zero_count'];self.assertEqual(zero['slot_pairs'],10);self.assertEqual(zero['decoded_tiles'],0)
    def test_nonvacuity_and_isolated_exceptional_checks(self):
        checks=self.proof['checks'];self.assertTrue(all(checks.values()))
        self.assertEqual(sum(k.startswith('quiet_nan_accumulator_payload_') for k in checks),4);self.assertEqual(sum(k.startswith('ordinary_accumulation_bits_') for k in checks),6)
        for name in ('isolated_exceptional_decode_bits','independent_row_input_mutation_discriminates','actual_weight_payload_mutation_discriminates'):self.assertTrue(checks[name])
        a=bytes.fromhex(self.cases['edge_base']['output_hex']);b=bytes.fromhex(self.cases['input_mutation']['output_hex']);self.assertNotEqual(a[:25600],b[:25600]);self.assertEqual(a[25600:],b[25600:]);self.assertNotEqual(a,bytes.fromhex(self.cases['live_weight_mutation']['output_hex']))
        self.assertEqual(self.cases['equal_inputs_full_overlap']['input_sha256'][0],self.cases['equal_inputs_full_overlap']['input_sha256'][1])
    def test_failed_candidates_and_diagnostic_signs_retained(self):
        first=read(P/'evidence/first-failure-retention.json');self.assertEqual(sha(P/first['failed_receipt']),first['failed_receipt_sha256']);self.assertEqual(sha(P/first['binary_copy']),first['binary_sha256'])
        d=read(P/'evidence/diagnostic-failure.json');self.assertFalse(d['passed'])
        attempt=P/d['attempt']
        for name,want in d['source_sha256'].items():self.assertEqual(sha(attempt/name),want,name)
        for path,want in d['artifact_sha256'].items():self.assertEqual(sha(P/path),want,path)
        result=d['result'];self.assertEqual(len(result['completed_case_summaries']),13);m=result['first_mismatch']
        self.assertEqual((m['row'],m['projection'],m['slot'],m['output_row']),(1,0,0,6));self.assertEqual(m['candidate_bf16'],0x7fc0);self.assertEqual(m['selected_bf16'],0xffc0);self.assertEqual(m['scalar_bf16'],0xffc0)
        self.assertTrue(m['status_equal']);self.assertFalse(m['output_equal']);self.assertEqual(m['diagnostic_candidate_paired_fp32_bits'],0x7fc00000)
        for k in ('diagnostic_selected_fp32_bits','diagnostic_scalar_fp32_bits','diagnostic_candidate_single_fp32_bits'):self.assertEqual(m[k],0xffc00000)
        self.assertTrue(result['owner_receipt']['safe_to_exit']);self.assertEqual(result['owner_receipt']['in_flight'],0);self.assertEqual(result['owner_receipt']['live_bytes'],0)
    def test_scope_and_owner_close(self):
        p=self.proof;self.assertEqual(p['geometry'],{'columns':2560,'rows':640,'top':10,'expert_table_entries':512,'materialized_banks':21,'row_bytes':820});self.assertFalse(p['device_executed'] or p['native_executed'] or p['model_executed'])
        r=p['owner_receipt'];self.assertTrue(r['safe_to_exit'] and r['idle_marker_complete']);self.assertEqual(r['backend'],'MockDevice');self.assertEqual(r['in_flight'],0);self.assertEqual(r['live_bytes'],0)
        self.assertIn('no Engine integration',p['scope']);self.assertIn('alias',p['scope'])
if __name__=='__main__':unittest.main()
