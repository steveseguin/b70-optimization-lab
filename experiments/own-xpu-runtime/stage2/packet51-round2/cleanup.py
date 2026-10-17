#!/usr/bin/env python3
"""Remove only this packet's regenerable CMake objects after passing CPU gates."""
import json
from pathlib import Path
from preparation import exclusive_cpu_work
from window_support import sha
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def main():
    with exclusive_cpu_work(0):
        protected=set()
        for name in ('build-layer-host.json','build-layer-device.json','cpu-layer-gates.json','cpu-candidate-gates.json','python-gates.json'):
            row=json.loads((HERE/name).read_text())
            assert row.get('passed') is True and row.get('device_executed') is False
            for field in ('source_hashes','artifacts','baseline_provenance','baseline_objects'):
                protected.update((ROOT/n).resolve() for n in row.get(field,{}))
        removed=[]
        for mode in ('host','device'):
            directory=HERE/'build'/mode/'CMakeFiles'
            for path in sorted(directory.rglob('*')):
                if not path.is_file() or not (path.name.endswith('.o') or path.name.endswith('.o.d')):continue
                assert not path.is_symlink() and path.resolve().is_relative_to((HERE/'build').resolve())
                assert path.resolve() not in protected, 'identity-bound evidence is not scratch'
                removed.append(dict(path=str(path.relative_to(HERE)),bytes=path.stat().st_size,sha256=sha(path)))
                path.unlink()
        row=dict(passed=True,device_executed=False,removed=removed,removed_bytes=sum(r['bytes'] for r in removed),
                 restore='Run build.py --kind host and then --kind device serially under the documented CPU limits.',
                 retained='All binaries, rejected binary, source mirrors, baseline relink proofs, logs and receipts remain.')
        (HERE/'cleanup.json').write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps(dict(passed=True,removed_files=len(removed),removed_bytes=row['removed_bytes'])))
if __name__=='__main__':main()
