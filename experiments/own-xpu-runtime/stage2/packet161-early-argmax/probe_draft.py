"""One CPU-only preparation feasibility probe with a hard 3.7 GB address cap.

No build or device library. A failed allocation closes this probe; no retry.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time
from audit import guard, P
from prepare import weight_admission


def main():
    guard()
    admission = weight_admission()
    binary = Path('/home/steve/own-xpu-runtime-results/packet49d-round3/build/gnu-host/own-rt-iq3')
    deps = subprocess.check_output(['readelf', '-d', str(binary)], text=True, stdin=subprocess.DEVNULL)
    assert not any(x in deps.lower() for x in ('libsycl', 'ze_loader', 'opencl', 'libcuda', 'libur_loader'))
    parent = P.parent/'packet132-two-candidate/build/capture/doc-0'
    inp = json.loads((parent/'input/input.json').read_text())
    result = json.loads((parent/'target/result.json').read_text())
    tokens = inp['tokens']+result['tokens']
    table = P/'evidence/draft-probe-idle.tsv'
    rows = []
    for pos in range(len(tokens)-1):
        path = parent/f'target/capture-streams/streams-{pos}.bf16'
        assert path.stat().st_size == 20480
        rows.append(f'{pos} {tokens[pos+1]} 1 {path}\n')
    table.write_text(''.join(rows))
    output = P/'evidence/draft-probe-idle'
    assert not output.exists()
    command = ['ionice', '-c', '3', str(binary), '--rank', '1', '--draft-capture', str(table), '--context', '128',
               '--plan', str(parent/'input/plan.tsv'), '--identity', str(parent/'input/identity.tsv'),
               '--model-dir', inp['model_dir'], '--output', str(output),
               '--dispatch', str(P.parent/'packet49d-round3/dispatch-speed6.json'), '--seconds', '10800']
    record = dict(argv=command, binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  admission=admission, address_cap_bytes=3_700_000_000, builds=False, device_executed=False)
    (P/'evidence/draft-probe-idle-command.json').write_text(json.dumps(record, indent=2)+'\n')
    env = dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    start = time.monotonic()
    def cap():
        resource.setrlimit(resource.RLIMIT_AS, (3_700_000_000, 3_700_000_000))
    with (P/'evidence/draft-probe-idle.log').open('w') as log:
        process = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=subprocess.STDOUT, preexec_fn=cap)
    record.update(returncode=process.returncode, seconds=time.monotonic()-start,
                  max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    (P/'evidence/draft-probe-idle-result.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
