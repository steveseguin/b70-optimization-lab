#!/usr/bin/env python3
"""CPU tests + SYCL compile/link only. No native target ever executed."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from plan import HERE, ROOT, CENSUS, make_plan, sha

def source_paths():
    kernels = HERE.parent/'packet2/kernels'
    return sorted([p for p in HERE.iterdir() if p.suffix in ('.py', '.cpp', '.hpp', '.patch', '.txt', '.json')
                   and p.name not in ('build-receipt.json', 'plan.json')]
                  + list(kernels.glob('*.hpp')) + [kernels/'device.cpp', CENSUS,
                    HERE.parent/'packet2/tests/device_window.py'])

def main():
    p = argparse.ArgumentParser(); p.add_argument('--keep-build', action='store_true'); a = p.parse_args()
    if os.environ.get('OMP_NUM_THREADS') != '2' or os.getpriority(os.PRIO_PROCESS, 0) != 19:
        raise SystemExit('nice 19 and OMP_NUM_THREADS=2 required')
    build = HERE/'build'
    scratch = [build/'owner', build/'compile', build/'plan.tsv']
    if any(path.exists() for path in scratch):
        raise SystemExit('build scratch exists; preserve the prior build before rebuilding')
    build.mkdir(exist_ok=True); record = dict(schema='own-runtime.h2d.build.v1', passed=False, native_executed=False,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(), commands=[], source_sha256={})
    def run(args, cwd=HERE):
        q = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        record['commands'].append(dict(argv=args, returncode=q.returncode, output=q.stdout))
        print(q.stdout, end='', flush=True)
        if q.returncode: raise RuntimeError('command failed: '+str(args))
    try:
        plan = make_plan(); (HERE/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
        record['source_sha256'] = {str(p.relative_to(ROOT)): sha(p) for p in source_paths()}
        (build/'owner').mkdir()
        pin = json.loads((HERE/'owner-source.json').read_text())
        for name, binding in pin['files'].items():
            contents = subprocess.check_output(['git','show',pin['commit']+':'+binding['path']],cwd=ROOT)
            target = build/'owner'/name; target.write_bytes(contents)
            if sha(target) != binding['sha256']: raise RuntimeError('pinned owner source mismatch')
        record['owner_source'] = pin
        run(['patch','--batch','--fuzz=0','-p1','-i',str(HERE/'independent-queues.patch')], build/'owner')
        record['patched_source_sha256'] = {p.name:sha(p) for p in (build/'owner').iterdir()}
        run([sys.executable,'-B','-m','unittest','-v','test_packet'])
        run(['cmake','-S',str(HERE),'-B',str(build/'compile'),'-DCMAKE_BUILD_TYPE=Release'])
        run(['cmake','--build',str(build/'compile'),'-j2'])
        run([str(build/'compile/owner-tests')])  # host-only executable; no SYCL linkage
        run(['readelf','-d',str(build/'compile/owner-tests')])
        record['binary_sha256'] = sha(build/'compile/h2d-native')
        record['compile_commands'] = json.loads((build/'compile/compile_commands.json').read_text())
        (build/'plan.tsv').write_text(''.join(f"{c['label']} {c['bytes']}\n" for c in plan['cases']))
        record['plan_tsv_sha256'] = sha(build/'plan.tsv')
        record['plan_json_sha256'] = sha(HERE/'plan.json')
        for path,digest in record['source_sha256'].items():
            if sha(ROOT/path) != digest: raise RuntimeError('source changed during build: '+path)
        record['passed'] = True
    finally:
        if not a.keep_build:
            for path in scratch:
                if path.is_dir(): shutil.rmtree(path)
                elif path.exists(): path.unlink()
            if not any(build.iterdir()): build.rmdir()
        record['build_directory_removed'] = not build.exists()
        record['build_scratch_removed'] = not any(path.exists() for path in scratch)
        (HERE/'build-receipt.json').write_text(json.dumps(record, indent=2)+'\n')
    return 0
if __name__ == '__main__': raise SystemExit(main())
