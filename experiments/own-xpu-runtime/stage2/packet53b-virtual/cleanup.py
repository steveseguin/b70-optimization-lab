#!/usr/bin/env python3
"""Remove only this packet's regenerable compiler objects after passing gates."""
import json
import shutil
from preparation import exclusive_cpu_work
from window_support import HERE, require, sha, save

def main():
    with exclusive_cpu_work():
        cpu=json.loads((HERE/'cpu-gates.json').read_text())
        require(cpu.get('passed') is True and cpu.get('device_executed') is False, 'CPU gates required before cleanup')
        removed=[]
        for mode in ('host','intel-host','device'):
            build=HERE/'build'/mode
            for path in sorted((build/'CMakeFiles').rglob('*')):
                if path.is_file() and (path.name.endswith('.o') or path.name.endswith('.o.d')):
                    require(path.resolve().is_relative_to(build.resolve()), 'scratch path escaped packet')
                    removed.append(dict(path=str(path.relative_to(HERE)),bytes=path.stat().st_size,sha256=sha(path)))
                    path.unlink()
        for name in ('cpu-smoke','intel-cpu-smoke'):
            source=HERE/'build'/name
            if source.exists():
                dest=HERE/'evidence-cpu'/('initial-'+name)
                require(not dest.exists(), 'initial evidence destination must be new')
                shutil.copytree(source,dest)
                for path in sorted(source.rglob('*')):
                    if path.is_file():
                        relative=path.relative_to(source)
                        require(sha(path)==sha(dest/relative),'evidence copy differs')
                        removed.append(dict(path=str(path.relative_to(HERE)),bytes=path.stat().st_size,
                                            sha256=sha(path),retained=str((dest/relative).relative_to(HERE))))
                shutil.rmtree(source)
        report=json.loads((HERE/'register-report.json').read_text())
        require(report.get('passed') is True,'register report required before scratch cleanup')
        for kernel in report['kernels']:
            require(sha(HERE.parents[3]/kernel['artifact'])==kernel['sha256'],'retained assembly differs')
        for scratch in (HERE/'build').glob('registers*'):
            require(scratch.is_dir() and scratch.resolve().is_relative_to((HERE/'build').resolve()),'register scratch path escaped')
            for path in scratch.rglob('*'):
                if path.is_file():removed.append(dict(path=str(path.relative_to(HERE)),bytes=path.stat().st_size,sha256=sha(path)))
            shutil.rmtree(scratch)
        final=sum(p.stat().st_size for p in (HERE/'build').rglob('*') if p.is_file())
        save(HERE/'cleanup.json',dict(passed=True,device_executed=False,removed=removed,
            removed_bytes=sum(r['bytes'] for r in removed),retained_build_bytes=final,
            restore='CPU-BUILD.md serial build commands regenerate compiler objects; retained baseline proofs and final binaries remain in place'))
        print(json.dumps(dict(passed=True,removed_bytes=sum(r['bytes'] for r in removed),retained_build_bytes=final)))

if __name__ == '__main__':
    main()
