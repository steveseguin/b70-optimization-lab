"""Create a fresh, fully bound packet77 placement/selection seal; CPU only."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from build_engine import P, ROOT, B, sha, save, limits


def main():
    limits()
    from run_screen import VIEW, verify_dependencies, WRAPPER
    verify_dependencies()
    require = lambda ok, message: None if ok else (_ for _ in ()).throw(ValueError(message))
    require(not (VIEW/'screen-seal.json').exists(), 'never replace a sealed view')
    build=json.loads((P/'build-device-receipt.json').read_text())
    gate=json.loads((P/'evidence/cpu-gates.json').read_text())
    reset=json.loads((P/'evidence/reset-gate.json').read_text())
    full=json.loads((P/'evidence/fullshape.json').read_text())
    for row in (gate,reset,full):require(row['passed'] and row['device_executed'] is False,'CPU gate missing')
    require(gate['build_receipt_sha256']==sha(P/'build-device-receipt.json'),'gate build changed')
    require(reset['binary_sha256']==sha(B/'gnu-host/own-rt-iq3'),'reset build changed')
    selection=json.loads((P/'selection.json').read_text())
    require(selection==json.loads((P.parent/'packet70-record-bundle/selection.json').read_text()),'packet70 selection differs')
    require(selection['choices']['experts']=='wide64' and selection['choices']['miss']=='batch','wrong selected view')
    # Feed the real full-shape post-load censuses through v4's unmodified gate.
    from placement import admission_gate
    memory=admission_gate(P)[1]
    ledger=json.loads((P/'memory-plan.json').read_text())
    admitted=[]
    for row in full['results']:
        census=json.loads((ROOT/row['census']).read_text())
        admitted.append(memory.check(census,ledger,row['result']['rank'],mtp=True,
                                     context=4096,draft_rank=1,target_split=0))
    save(P/'evidence/fullshape-admission.json',dict(passed=True,device_executed=False,admissions=admitted))
    sources={**build['sources'],**gate['sources'],**full['sources']}
    sources.update(json.loads((P/'dependency-pins.json').read_text()))
    for path in [*P.glob('*.py'),P/'attribution.hpp',P/'selection.json',P/'selection-decision.json',
                 P/'dependency-pins.json',* (P/'evidence').glob('*.json'),*(P/'evidence').glob('*.log')]:
        if path.name not in {'screen-plan.json','queue-plan.json','final-check.json','queue-plan-B.log'}:
            sources[str(path.relative_to(ROOT))]=sha(path)
    for name,digest in sources.items():require(sha(ROOT/name)==digest,'changed source: '+name)
    VIEW.mkdir(parents=True)
    for leaf in ('selection.json','selection-decision.json','dispatch-speed6.json','memory-plan.json'):
        (VIEW/leaf).write_bytes((P/leaf).read_bytes())
    binary=VIEW/'build/device/own-rt-iq3';binary.parent.mkdir(parents=True)
    os.link(B/'device/own-rt-iq3',binary)
    audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,
        binary_sha256=sha(binary),dispatch_sha256=sha(VIEW/'dispatch-speed6.json'),
        engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in
            ('main.cpp','rank.hpp','mtp.hpp','p56_config.hpp','p56_prefix.hpp','strict_snapshot.hpp','p49d_submit.cpp','attribution.hpp')},
        rationale='Packet70 24/24 rank1 draft and full resident head; exact selected wide64/batch/draft-HC view. Only observation changed. Full production post-load mock allocation and real memory admission passed.')
    save(VIEW/'placement-audit.json',audit)
    plan=dict(schema='packet77.attribution-plan.v1',lane='B',placement='1',
        arms=['control','attribution'],control_reset_token=1,attribution_reset_token=0,
        model_lifetimes=1,requests=25,tokens=[64]+[128]*24,sample_generated_indices=[9,16],
        target_layers_sampled={'0':[22,23],'1':[24,27]},target_layers=[24,24],draft_rank=1,
        expected_work_seconds=420,watchdog_seconds=3600,duration_is_estimate=True,
        report_after_lane_release=True,qualifying=False,device_measurements='pending')
    save(VIEW/'attribution-plan.json',plan)
    for name in ('placement-audit.json','attribution-plan.json','selection-decision.json'):
        sources[str((VIEW/name).relative_to(ROOT))]=sha(VIEW/name)
    for key in ('expected','actual'):
        os.link(P/'evidence'/('fixture-'+key+'.bin'),VIEW/('fixture-'+key+'.bin'))
    bp=VIEW/'build-receipt.json';fp=VIEW/'byte-fixture.json'
    save(bp,dict(passed=True,device_executed=False,sources=sources,
                 artifacts={'build/device/own-rt-iq3':sha(binary)}))
    save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
        build_receipt_sha256=sha(bp),sources=gate['sources'],
        changed_class='Observation only: target fixtures, tokens, draft proposals/state match packet65 binary with packet70 selection; repeated attribution and one-load reset toggles.',
        command=[sys.executable,'-B',str(P/'cpu_gate.py')],
        **{key:dict(path='fixture-'+key+'.bin',sha256=sha(VIEW/('fixture-'+key+'.bin'))) for key in ('expected','actual')}))
    spec=importlib.util.spec_from_file_location('generic_seal',P.parent/'screen/seal.py')
    generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
    generic.create(VIEW,'tp2',bp,fp,binary,VIEW/'dispatch-speed6.json',VIEW/'screen-seal.json')
    row=json.loads((VIEW/'screen-seal.json').read_text());row['timing_modes']=['attribution']
    row['attribution_plan']=plan;save(VIEW/'screen-seal.json',row)
    print('packet77 selected view sealed; real 24/24 full-shape admission PASS')


if __name__=='__main__':main()
