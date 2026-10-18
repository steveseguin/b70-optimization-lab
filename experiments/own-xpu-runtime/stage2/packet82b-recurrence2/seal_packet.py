# Retained ancestor implementation; not an entrypoint for packet84.
if __name__ == '__main__':
    raise SystemExit('Retired inherited entrypoint. Use build_engine.py, cpu_gate.py, composed_cpu.py, full_shape.py, prepare_chain.py, prepare_packet.py, then fast_reseal.py; see README.md.')
#!/usr/bin/env python3
"""Seal all eight views, reusing one engine and completed CPU fixtures."""
import json
import os
import subprocess
import sys
from pathlib import Path
from build_engine import sha, save
from prepare_selections import configs
from bundle_selection import PLACEMENTS
P = Path(__file__).resolve().parent
ROOT = P.parents[3]

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    build = json.loads((P/'build-device-receipt.json').read_text())
    gate = json.loads((P/'evidence/cpu-gates.json').read_text())
    assert gate['passed'] and gate['build_receipt_sha256'] == sha(P/'build-device-receipt.json')
    sources = dict(build['sources'], **gate['sources'])
    for name, digest in sources.items(): assert sha(ROOT/name) == digest, name
    for f in (P/'seal_packet.py', P/'build-device-receipt.json', P/'evidence/cpu-gates.json'):
        sources[str(f.relative_to(ROOT))] = sha(f)
    for placement, (rank, split, boundary) in PLACEMENTS.items():
        for kernel_name, config in configs().items():
            name = placement + '-' + kernel_name
            dest = P/'selections'/name
            dest.mkdir()
            save(dest/'selection.json', config)
            for leaf in ('selection-decision.json', 'memory-plan.json', 'dispatch-speed6.json'):
                (dest/leaf).write_bytes((P/leaf).read_bytes())
            binary = dest/'build/device/own-rt-iq3'
            binary.parent.mkdir(parents=True)
            os.link(P/'build/device/own-rt-iq3', binary)
            audit = dict(placement=placement, draft_rank=rank, target_split=split, layer_boundary=boundary,
                         binary_sha256=sha(binary), dispatch_sha256=sha(dest/'dispatch-speed6.json'),
                         engine_sources={str((P/leaf).relative_to(ROOT)):sha(P/leaf) for leaf in
                           ('main.cpp','rank.hpp','mtp.hpp','p56_config.hpp','p56_prefix.hpp','strict_snapshot.hpp','p49d_submit.cpp')},
                         rationale='Both placements retain the shared full head on rank1. K2 dispatch keys are operator classes, independent of layer ownership; full chain still requires fresh exactness.')
            save(dest/'placement-audit.json', audit)
            scoped = dict(sources)
            for leaf in ('selection.json','selection-decision.json','memory-plan.json','dispatch-speed6.json','placement-audit.json'):
                scoped[str((dest/leaf).relative_to(ROOT))] = sha(dest/leaf)
            for key in ('expected','actual'):
                os.link(P/'evidence'/(kernel_name+'-'+key+'.bin'), dest/('fixture-'+key+'.bin'))
            save(dest/'build-receipt.json', dict(passed=True, device_executed=False, sources=scoped,
                artifacts={'build/device/own-rt-iq3':sha(binary)}, selection=name))
            save(dest/'fixture.json', dict(schema='own-runtime.screen.byte-fixture.v1', passed=True,
                device_executed=False, build_receipt_sha256=sha(dest/'build-receipt.json'), sources=scoped,
                changed_class='Packet64 combined draft HC and batched copies; packet56 target fixtures and fresh draft repeats',
                command=[sys.executable,'-B',str(P/'cpu_gate.py')],
                **{key:dict(path='fixture-'+key+'.bin',sha256=sha(dest/('fixture-'+key+'.bin'))) for key in ('expected','actual')}))
            subprocess.run([sys.executable,'-B',str(P.parent/'screen/seal.py'),'--profile','tp2','--lineage',str(dest),
                '--build-receipt',str(dest/'build-receipt.json'),'--fixture',str(dest/'fixture.json'),
                '--binary',str(binary),'--dispatch',str(dest/'dispatch-speed6.json'),'--output',str(dest/'screen-seal.json')], check=True)
            print(name, 'sealed', flush=True)

if __name__ == '__main__': main()
