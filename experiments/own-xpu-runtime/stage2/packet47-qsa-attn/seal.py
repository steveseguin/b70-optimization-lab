#!/usr/bin/env python3
"""Bind packet47 CPU evidence and compile-only device artifact. No device use."""
from datetime import datetime, timezone
import json
import os
from window_support import HERE, REPO, require, sha, verify_files

GATES = ('build-host.json', 'build-device.json', 'cpu-gates.json', 'python-gates.json')


def main():
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity required')
    sources, artifacts, gates = {}, {}, {}
    def merge(mapping):
        verify_files(mapping, REPO)
        for name, digest in mapping.items():
            require(name not in sources or sources[name] == digest, 'conflicting source pin: '+name)
            sources[name] = digest
    rows = {}
    for name in GATES:
        path = HERE/name
        row = json.loads(path.read_text())
        require(row.get('passed') is True and row.get('device_executed') is False, 'CPU gate failed: '+name)
        merge(row.get('source_hashes', row.get('sources', {})))
        for artifact, digest in row.get('artifacts', {}).items():
            require(artifact not in artifacts or artifacts[artifact] == digest, 'artifact conflict')
            artifacts[artifact] = digest
        rows[name] = row
        gates[name] = sha(path)
    verify_files(artifacts, HERE)
    require('build/device/qsa-bench' in artifacts, 'device binary missing')
    cpu = rows['cpu-gates.json']
    require(cpu.get('fresh_process_repeats_equal') is True, 'two fresh CPU repeats required')
    require(cpu.get('build_receipt_sha256') == gates['build-host.json'], 'CPU gate/build identity mismatch')
    require(cpu.get('cross_compiler_outputs_equal') is True, 'cross-compiler agreement required')
    repeats=cpu.get('repeats',[])
    require(len(repeats)==4 and {(r['compiler'],r['repeat']) for r in repeats}==
            {(c,r) for c in ('gnu','intel') for r in (1,2)}, 'complete four CPU owners required')
    require(len({r['summary']['pid'] for r in repeats})==4, 'CPU processes not fresh')
    require(len({r['raw_sha256'] for r in repeats})==1, 'CPU raw outputs differ')
    for repeat in repeats:
        require(repeat['summary'].get('passed') is True and len(repeat['case_rows'])==36,
                'CPU case matrix incomplete')
        verify_files(repeat['files'], HERE)
    verify_files(cpu['evidence'], HERE)
    # Evidence is included in the seal, never merely a mutable passed boolean.
    artifacts.update(cpu['evidence'])
    own = [p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py','.sh','.cpp','.hpp')]
    own += [HERE/name for name in ('PREREGISTRATION.md','WINDOW.md','ORACLE.md')]
    own += list((HERE/'analysis').glob('*'))
    merge({str(p.relative_to(REPO)):sha(p) for p in own})
    result = dict(schema='own-runtime.packet47.seal.v1', passed=True, device_executed=False,
        device_qualified=False, model_speed_claim=False, card=0,
        contexts=[1024,2048,4096,8192,32768], rows=[1,2], bar_4k_attention_speedup=3,
        order_preserving_preference_speedup=5, sources=sources, artifacts=artifacts, gates=gates,
        completed_utc=datetime.now(timezone.utc).isoformat(),
        pending=['card-0 E1/E2 exact CPU oracle and fresh determinism',
                 'card-0 T1/T2 per-class performance at every registered shape',
                 'full-engine new-oracle/logit/token qualification if split tree selected'])
    (HERE/'seal.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True, seal_sha256=sha(HERE/'seal.json'),sources=len(sources),artifacts=len(artifacts),device_executed=False)))

if __name__ == '__main__':
    main()
