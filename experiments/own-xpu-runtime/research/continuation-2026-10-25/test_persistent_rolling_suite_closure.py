import copy
import difflib
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import persistent_rolling_suite_audit as audit


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def record(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p))
def write(p,d):p.write_text(json.dumps(d));return p


def fixture(root):
    binary=root/'own-engine';binary.write_bytes(b'fixed native binary')
    build=write(root/'build-receipt.json',dict(schema='ownrt.engine.build.v1',binary=str(binary),binary_sha256=digest(binary)))
    planner=root/'persistent_rolling_driver.py';planner.write_text('def make_plan(config):\n    return config\n\ndef execute(plan):\n    return plan\n')
    runtime=root/'persistent_rolling_suite.py';runtime.write_text('RUNTIME = 1\n')
    def plan(name,policy):
        output=root/name;config=root/(name+'-config.json');suite=root/(name+'-suite.json');write(config,{});write(suite,{})
        pins={str(p):digest(p) for p in (config,suite,binary,build,planner,runtime)}
        args=[str(binary),'--shared',str(output/'stage0/shared.bin'),'--output',str(output/'stage0/native'),'--max-new','32',
              '--seconds','1800','--pipeline-ring-request-sha256',name,'--pipeline-ring-check-policy',policy]
        if policy=='qualification':args+=['--pipeline-ring-verify-restore','--pipeline-ring-recursive-verify-restore','--pipeline-ring-verify-provider-survival']
        stage=dict(id=0,first=True,final=True,begin=0,end=48,bdf='x',packed_weight_bytes=9,argv=args,environment={
            'SYCL_CACHE_DIR':str(output/'stage0/cache/sycl'),'NEO_CACHE_DIR':str(output/'stage0/cache/neo'),
            'XDG_CACHE_HOME':str(output/'stage0/cache/xdg'),'ARITHMETIC':'exact'})
        return dict(config=str(config),suite=str(suite),pins=pins,output=str(output),check_policy=policy,request_sha256=name,max_new=32,
            seconds=1800,stages=[stage],model_identity_sha256='m',draft_model_sha256='d',draft_experts='fp8',context=4096,vocab=248320,
            activation_dtype='F32',boundaries=[0,48],eos_token_ids=[7])
    return plan('qualified','qualification'),plan('measured','measured'),planner,runtime


def bridge(root,planner,before):
    old=root/'before.py';old.write_bytes(before)
    delta=root/'planner.patch';delta.write_text(''.join(difflib.unified_diff(before.decode().splitlines(True),planner.read_text().splitlines(True),
        fromfile='before/persistent_rolling_driver.py',tofile='after/persistent_rolling_driver.py')))
    binding=dict(passed=True,planner_before_sha256=digest(old),planner_after_sha256=digest(planner),planner_patch_sha256=digest(delta))
    cpu=write(root/'cpu.json',binding);review=write(root/'review.json',binding)
    path=write(root/'transition.json',dict(schema='ownrt.persistent-rolling-planner-transition.v1',passed=True,scope='trace-budget-only',
        source_path=str(planner),before_source=record(old),after_source=record(planner),patch=record(delta),cpu_review=record(cpu),independent_review=record(review)))
    return path


class ClosureTests(unittest.TestCase):
    def test_exact12_baseline_arrays_not_silent_zip_truncation(self):
        baseline=Path(__file__).parent/'persistent-rolling-baseline-audit.json';original=audit.read
        for filename,key in [(baseline.name,'rows'),('suite.json','prompts'),('suite-result.json','prompts')]:
            def changed(path):
                data=original(path)
                if Path(path).name==filename:data=copy.deepcopy(data);data[key].pop()
                return data
            with self.subTest(file=filename),patch.object(audit,'read',side_effect=changed),self.assertRaises(ValueError):audit.load_baseline(baseline)

    def test_exact_native_build_execution_closure_and_explicit_run_differences(self):
        with tempfile.TemporaryDirectory() as folder:
            old,current,planner,runtime=fixture(Path(folder))
            self.assertTrue(audit.validate_prerequisite_closure(current,old)['passed'])
            current['max_new']=512;current['stages'][0]['argv'][current['stages'][0]['argv'].index('--max-new')+1]='512'
            current['ring_trace_limit']=4096;current['stages'][0]['argv']+=['--pipeline-ring-trace-limit','4096']
            self.assertTrue(audit.validate_prerequisite_closure(current,old)['passed'])
            for kind in ('native','runtime','inventory','environment','kernel'):
                bad=copy.deepcopy(current)
                if kind=='native':bad['pins'][str(Path(folder)/'own-engine')]='0'*64
                elif kind=='runtime':bad['pins'][str(runtime)]='0'*64
                elif kind=='inventory':bad['pins'][str(Path(folder)/'extra.py')]='1'*64
                elif kind=='environment':bad['stages'][0]['environment']['ARITHMETIC']='changed'
                else:bad['stages'][0]['argv']+=['--other-arithmetic']
                with self.subTest(kind=kind),self.assertRaises(ValueError):audit.validate_prerequisite_closure(bad,old)

    def test_trusted_reviewed_make_plan_only_bridge_and_all_refusals(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old,current,planner,runtime=fixture(root);before=planner.read_bytes()
            planner.write_text(planner.read_text().replace('return config','return dict(config, trace_limit=4096)'))
            current['pins'][str(planner)]=digest(planner);path=bridge(root,planner,before)
            with self.assertRaises(ValueError):audit.validate_prerequisite_closure(current,old)
            checked=audit.load_planner_transition(path,digest(path))
            self.assertEqual(audit.validate_prerequisite_closure(current,old,checked)['changed_source_paths'],[str(planner)])
            with self.assertRaises(ValueError):audit.load_planner_transition(path,'0'*64)
            # Even a rehashed/reviewed bridge cannot change execute or module code.
            planner.write_text(planner.read_text().replace('return plan','return None'));path=bridge(root,planner,before)
            with self.assertRaisesRegex(ValueError,'outside make_plan'):audit.load_planner_transition(path,digest(path))
            planner.write_bytes(before.replace(b'return config',b'return dict(config)'));path=bridge(root,planner,before)
            receipt=json.loads(path.read_text());review=Path(receipt['independent_review']['path']);data=json.loads(review.read_text())
            data['planner_after_sha256']='0'*64;write(review,data);receipt['independent_review']=record(review);write(path,receipt)
            with self.assertRaisesRegex(ValueError,'does not bind'):audit.load_planner_transition(path,digest(path))

    def test_accepted_summary_binds_copied_plan_and_qualification_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan=write(root/'plan.json',{'native':'fixed'});qualified=write(root/'qualified.json',{'proof':'checked'})
            summary=dict(schema='ownrt.persistent-rolling-proof.v1',passed=True,requests=2,check_policy='measured',
                all_requests_full_state_parity=True,provenance_passed=True,target_state_exact=True,draft_state_exact=True,
                output_tokens_exact=True,original_plan=record(plan),qualified_reference_parity=True,qualified_reference=record(qualified))
            audit.validate_prerequisite_record(summary,plan,'measured',qualified)
            write(plan,{'native':'replacement'})
            with self.assertRaisesRegex(ValueError,'copied plan'):audit.validate_prerequisite_record(summary,plan,'measured',qualified)
            summary['original_plan']=record(plan);write(qualified,{'proof':'other'})
            with self.assertRaisesRegex(ValueError,'another qualification'):audit.validate_prerequisite_record(summary,plan,'measured',qualified)

    def test_actual_qualified_and_measured_native_execution_identities(self):
        here=Path(__file__).parent
        old=audit.read(here/'ring-persistent-qualified-b-plan.json');current=audit.read(here/'ring-persistent-measured-plan.json')
        result=audit.validate_prerequisite_closure(current,old)
        self.assertEqual(result['native_binary']['sha256'],'02a47c059444af0e9179612461a8078e4308f3357fb54e370421a2ba1b7788aa')
        self.assertEqual(result['changed_source_paths'],[])


if __name__=='__main__':unittest.main()
