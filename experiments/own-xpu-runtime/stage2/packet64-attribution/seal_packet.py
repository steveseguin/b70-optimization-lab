#!/usr/bin/env python3
"""Seal the fixed 24/24 production-draft attribution selection after CPU gates."""
import json
import os
import subprocess
import sys
from build_engine import limits, sha, save, P, ROOT, BASE


def main():
    limits()
    build = json.loads((P/'build-device-receipt.json').read_text())
    gate = json.loads((P/'evidence/cpu-gates.json').read_text())
    assert gate['passed'] and gate['build_receipt_sha256']==sha(P/'build-device-receipt.json')
    reset = json.loads((P/'evidence/reset-gate.json').read_text())
    assert reset['passed'] and reset['binary_sha256']==sha(P/'build/gnu-host/own-rt-iq3')
    with (P/'evidence/attribution-tests.log').open('w') as log:
        subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_attribution.py','-v'],
                       check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    sources = dict(build['sources'], **gate['sources'])
    for name,digest in sources.items(): assert sha(ROOT/name)==digest, name
    for name in ('seal_packet.py','build-device-receipt.json','evidence/cpu-gates.json','summarize.py','timeline.py','test_attribution.py',
                 'reset_gate.py','evidence/reset-gate.json','evidence/attribution-tests.log'):
        sources[str((P/name).relative_to(ROOT))] = sha(P/name)
    # Bind the actual local Python import closure used by the CPU fixtures,
    # as well as the observation-reset helper exercised on the host pair.
    for path in [*P.glob('*.py'), P.parent/'screen/v3-attr/tp2_worker.py']:
        sources[str(path.relative_to(ROOT))] = sha(path)
    dest=P/'selections/1-production-control'
    dest.mkdir(parents=True)
    for name in ('selection.json','selection-decision.json','memory-plan.json','dispatch-speed6.json'):
        (dest/name).write_bytes((P/name).read_bytes())
    assert sha(dest/'selection.json')==sha(BASE/'selections/1-production-control/selection.json')
    binary=dest/'build/device/own-rt-iq3'
    binary.parent.mkdir(parents=True)
    os.link(P/'build/device/own-rt-iq3',binary)
    audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,
        binary_sha256=sha(binary),dispatch_sha256=sha(dest/'dispatch-speed6.json'),
        engine_sources={str((P/leaf).relative_to(ROOT)):sha(P/leaf) for leaf in
            ('main.cpp','rank.hpp','mtp.hpp','p56_config.hpp','p56_prefix.hpp','strict_snapshot.hpp','p49d_submit.cpp','attribution.hpp')},
        rationale='Packet64 unchanged target/draft arithmetic, spin and HC fusion; 24/24, rank1 production draft. Observation only.')
    save(dest/'placement-audit.json',audit)
    plan=dict(schema='packet64.attribution.plan.v1',placement='1',target_layers=[24,24],draft_rank=1,
        draft='production',miss='control',sample_generated_indices=[9,16],
        target_layers_sampled={'0':{'GDN':22,'QSA':23},'1':{'GDN':24,'QSA':27}},
        target_layer_counts_per_rank={'GDN':18,'QSA':6},
        arms=['control','attribution'],control_reset_token=1,attribution_reset_token=0,
        requests=25,model_lifetimes=1,expected_work_seconds=600,
        duration_status='planning estimate only; admission/hold waits excluded',
        instrumentation='packet57 events at existing drains; no new kernel barriers',
        layer_span_boundaries={'0':['blk.0.hc.a.norm','blk.23.ffn.combine'],
                               '1':['blk.24.hc.a.norm','blk.47.ffn.combine']},
        control='Same loaded binary/weights, full state reset, 12x128 uninstrumented then 12x128 instrumented; incident64 first',
        oracle='packet49-integrate',qualifying=False)
    save(dest/'attribution-plan.json',plan)
    for name in ('placement-audit.json','attribution-plan.json','selection.json','selection-decision.json','memory-plan.json','dispatch-speed6.json'):
        sources[str((dest/name).relative_to(ROOT))]=sha(dest/name)
    for key in ('expected','actual'):
        os.link(P/'evidence'/('fixture-'+key+'.bin'),dest/('fixture-'+key+'.bin'))
    save(dest/'build-receipt.json',dict(passed=True,device_executed=False,sources=sources,
         artifacts={'build/device/own-rt-iq3':sha(binary)}))
    save(dest/'fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
         build_receipt_sha256=sha(dest/'build-receipt.json'),sources=sources,
         changed_class='Instrumentation only; 96 target fixtures, 24 tokens, draft proposals/state match packet64; two fresh repeats',
         command=[sys.executable,'-B',str(P/'cpu_gate.py')],
         **{key:dict(path='fixture-'+key+'.bin',sha256=sha(dest/('fixture-'+key+'.bin'))) for key in ('expected','actual')}))
    subprocess.run([sys.executable,'-B',str(P.parent/'screen/seal.py'),'--profile','tp2','--lineage',str(dest),
         '--build-receipt',str(dest/'build-receipt.json'),'--fixture',str(dest/'fixture.json'),
         '--binary',str(binary),'--dispatch',str(dest/'dispatch-speed6.json'),'--output',str(dest/'screen-seal.json')],
         check=True,stdin=subprocess.DEVNULL)
    # Finalize the initial seal before any consumer runs. No existing seal is replaced.
    seal=json.loads((dest/'screen-seal.json').read_text())
    seal.update(timing_modes=['attribution'],attribution_plan=plan)
    save(dest/'screen-seal.json',seal)
    print('sealed',sha(dest/'screen-seal.json'))

if __name__=='__main__':main()
