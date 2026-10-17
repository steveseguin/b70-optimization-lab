#!/usr/bin/env python3
"""Bind source, binaries and completed CPU-only gates before coordinator use."""
import json
from preparation import limits
from window_support import HERE, REPO, require, sha, save, verify_files

def main():
    admission=limits(); sources={}; artifacts={}; build_rows={}
    for mode in ('host','intel-host','device'):
        path=HERE/f'build-{mode}.json'
        row=json.loads(path.read_text())
        require(row.get('passed') is True and row.get('device_executed') is False and row.get('mode') == mode, 'incomplete build')
        verify_files(row['source_hashes'],REPO)
        verify_files(row['artifacts'],REPO)
        verify_files(row['baseline_provenance'],REPO)
        for name, detail in row['baseline_objects'].items():
            require(sha(REPO/name) == detail['sha256'], 'baseline object drift')
        sources.update(row['source_hashes'])
        artifacts.update({str((REPO/name).relative_to(HERE)):h for name,h in row['artifacts'].items()})
        artifacts[path.name]=sha(path)
        build_rows[mode]=dict(receipt=path.name,sha256=sha(path))
    build=dict(schema='own-runtime.packet53.build-receipt.v1',passed=True,device_executed=False,
               builds=build_rows,source_hashes=sources,artifacts=artifacts,admission=admission)
    save(HERE/'build-receipt.json',build)
    cpu=json.loads((HERE/'cpu-gates.json').read_text())
    require(cpu.get('passed') is True and cpu.get('device_executed') is False, 'CPU arithmetic gate incomplete')
    require(cpu['build_receipt_sha256'] == sha(HERE/'build-host.json'), 'CPU build changed')
    require(cpu['intel_build_receipt_sha256'] == sha(HERE/'build-intel-host.json'), 'Intel CPU build changed')
    verify_files(cpu['sources'],REPO);verify_files(cpu['artifacts'],REPO)
    require(len(cpu['runs']) == 4 and len({r['comparisons_sha256'] for r in cpu['runs']}) == 1, 'fresh CPU equality incomplete')
    require({(r['compiler'],r['repeat']) for r in cpu['runs']} == {(m,i) for m in ('host','intel-host') for i in (0,1)}, 'CPU compiler/fresh-run census')
    require(len(cpu['full_runs']) == 2 and len({r['comparisons_sha256'] for r in cpu['full_runs']}) == 1, 'fresh full CPU equality incomplete')
    for run in cpu['runs'] + cpu['full_runs']:
        verify_files(run['files'],REPO)
        sources.update(run['files'])
    sanitizer=cpu['sanitizer']
    require(sanitizer.get('passed') is True and sanitizer.get('device_executed') is False
            and sanitizer['output_sha256']==cpu['runs'][0]['output_sha256'], 'sanitizer equality incomplete')
    verify_files(sanitizer['files'],REPO);sources.update(sanitizer['files'])
    artifacts.update({str((REPO/name).relative_to(HERE)):h for name,h in cpu['artifacts'].items()})
    py=json.loads((HERE/'python-gates.json').read_text())
    require(py.get('passed') is True and py.get('device_executed') is False, 'Python gates incomplete')
    verify_files(py['sources'],REPO)
    for p in HERE.iterdir():
        if p.is_file() and (p.suffix in ('.py','.sh','.cpp','.hpp','.md') or p.name in ('CMakeLists.txt','manifest.json')):
            sources[str(p.relative_to(REPO))]=sha(p)
    for p in (HERE.parent/'packet34-replay-bench/window.py',HERE.parent/'packet51-round2/window_support.py'):
        sources[str(p.relative_to(REPO))]=sha(p)
    gates={name:sha(HERE/name) for name in ('build-receipt.json','cpu-gates.json','python-gates.json')}
    save(HERE/'seal.json',dict(schema='own-runtime.packet53.seal.v1',passed=True,device_executed=False,
        device_qualified=False,model_speed_claim=False,expert_order_proceeds=None,
        sources=sources,artifacts=artifacts,gates=gates,pending=['coordinator E1/E2','coordinator T1/T2','two-owner decision']))
    from window_support import sealed_gate
    sealed_gate()
    print(json.dumps(dict(passed=True,device_executed=False,seal_sha256=sha(HERE/'seal.json'),build_bytes=admission['build_bytes'])))

if __name__ == '__main__':
    main()
