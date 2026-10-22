"""The chain's own transport against the k3x engine, CPU only (the packet155 W0p failure, closed).

packet155-chain-a stopped in W0p: both ranks exited with `shared extent` because the chain transport
created packet136's 3*SLOT+4096-byte shared file while the v5 engine maps 4*SLOT+4096+64 bytes.
This gate runs packet190's REAL chain code with packet190's gnu-host k3x engine (same sources as the
device engine), in CPU miniature mode:

1. W0p: window.concurrency_canary() exactly as the chain calls it (1000 handovers, both ranks alive,
   overlapping work), through packet190's chain_pipeline.Transport;
2. negative control: the same canary with the old 3*SLOT+4096 shared size must fail in both ranks
   with `shared extent` (packet155's failure, reproduced on CPU);
3. decode: chain_pipeline.run() (native controller, MTP draft, 24 tokens, all 120 layer fixtures of the
   five-layer miniature --pipeline-mini5, packet188/189's k3-storage reference shape) for a
   miniature bundle-8 selection and the miniature k3x selection (boundary=rank0-k3, kernel_io=kernel,
   rank0_prepare=async, boundary_export=copy, static): identical tokens, fixtures (merged over ranks), draft
   proposals; k3x issued boundary commands.
"""
import hashlib, json, os, resource, shutil, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
O = Path(__file__).resolve().parent
ROOT = O.parents[3]
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x'
SRC = ROOT / 'experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/v5/build/k3-state/selections'
sys.path.insert(0, str(P))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def selections(root):
    out = {}
    for name in ('production', 'k3x'):
        src = SRC / (name + '.json')
        dst = root / name
        dst.mkdir()
        shutil.copyfile(src, dst / 'selection.json')
        out[name] = (dst, sha(dst / 'selection.json'))
    return out


def arguments(pp, binary, out, extra=()):
    return pp.parser().parse_args(['--binary', str(binary), '--output', str(out), '--mini', '--context', '256', '--tokens', '24',
                                   '--seconds', '600', '--wait-seconds', '300', '--native-nice', '19', '--draft', 'mtp', '--draft-rank', '1',
                                   '--target-split', '0', '--controller', 'native', '--timing', 'token', '--retain-steps', '1-24', *extra])


def canary(pp, window, binary, root, adapter, digest, label):
    out = root / label
    out.mkdir()
    args = arguments(pp, binary, out / 'unused')
    args.selection_sha256 = digest
    args.host_memory = 'resident'
    watch = SimpleNamespace(check=lambda: None, mark_launched=lambda pid: None, latch=lambda e: None)
    env = {'PATH': '/usr/bin:/bin', 'OMP_NUM_THREADS': '2'}
    with patch.object(pp, 'P', adapter), patch.object(window, 'admit_output', lambda *a, **k: None):
        return window.concurrency_canary(args, out, env, watch)


def decode(pp, binary, root, adapter, digest, label):
    out = root / label
    args = arguments(pp, binary, out)
    args.selection_sha256 = digest
    args.host_memory = 'resident'
    real = pp.subprocess.Popen

    def popen(cmd, *a, **k):  # packet188/189: the k3 storage (rank0_layers 0-26) needs the five-layer miniature; the reference runs it too
        cmd = list(cmd)
        assert '--mini' in cmd
        return real(cmd + ['--pipeline-mini5'], *a, **k)
    with patch.object(pp, 'P', adapter), patch.object(pp.subprocess, 'Popen', popen):
        r = pp.run(args)
    fixtures = {}
    for rank in (0, 1):
        for f in (out / f'rank{rank}').glob('step*/layer-*.bf16'):
            key = f.parent.name + '/' + f.name
            assert key not in fixtures, 'fixture produced by both ranks: ' + key
            fixtures[key] = sha(f)
    proposals = [json.loads(x).get('guess') for x in (out / 'rank1/draft-rows.jsonl').read_text().splitlines() if x.strip()]
    boundaries = sum(1 for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15)
    return dict(tokens=r['tokens'], stats={k: r['stats'][k] for k in ('guesses', 'hits', 'misses', 'no_guess')}, fixtures=fixtures,
                proposals=proposals, boundaries=boundaries)


def main():
    assert shutil.disk_usage('/').free >= 27_000_000_000
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    os.environ['OMP_NUM_THREADS'] = '2'
    import chain_pipeline as pp
    import window
    from reuse_build import verify_native
    native = verify_native()
    binary = P / 'build/gnu-host/own-rt-iq3'
    assert pp.SHARED == 4 * pp.SLOT + 4096 + 64
    rows = {}
    with tempfile.TemporaryDirectory(prefix='p190-transport-', dir=P / 'build') as tmp:
        root = Path(tmp)
        sel = selections(root)
        rows['w0p_canary_k3x'] = canary(pp, window, binary, root, *sel['k3x'], 'canary-k3x')
        assert rows['w0p_canary_k3x']['passed'] and rows['w0p_canary_k3x']['handovers'] == 1000
        old = 3 * pp.SLOT + 4096
        refused = None
        with patch.object(pp, 'SHARED', old):
            try:
                canary(pp, window, binary, root, *sel['k3x'], 'canary-old-shared')
            except Exception as error:  # the chain transport raises after both ranks exit
                refused = str(error)
        failures = [(root / 'canary-old-shared/run' / f'rank{r}/failure.txt') for r in (0, 1)]
        texts = [f.read_text().strip() if f.exists() else '' for f in failures]
        assert refused is not None and all('shared extent' in t for t in texts), (refused, texts)
        rows['negative_old_shared_size'] = dict(refused=True, error=refused[:200], rank_failures=texts, shared_bytes=old)
        reference = decode(pp, binary, root, *sel['production'], 'decode-production')
        k3x = decode(pp, binary, root, *sel['k3x'], 'decode-k3x')
        assert reference['boundaries'] == 0 and k3x['boundaries'] > 0
        for key in ('tokens', 'stats', 'fixtures', 'proposals'):
            assert k3x[key] == reference[key], 'k3x differs from the bundle-8 miniature through the chain transport: ' + key
        assert len(k3x['fixtures']) == 120 and len(k3x['tokens']) == 24  # five-layer miniature: 5 x 24
        rows['decode'] = dict(tokens=len(k3x['tokens']), fixtures=len(k3x['fixtures']), stats=k3x['stats'], k3x_boundaries=k3x['boundaries'], identical=True)
    row = dict(passed=True, device_executed=False, schema='packet190.transport-gate.v1', chain_shared_bytes=pp.SHARED,
               engine_binary_sha256=sha(binary), device_binary_sha256=native['binaries']['build/device/own-rt-iq3']['sha256'],
               selections={k: v[1] for k, v in sel.items()}, rows=rows,
               sources={str(f.relative_to(ROOT)): sha(f) for f in (Path(__file__), P / 'chain_pipeline.py', P / 'pipeline.py', P / 'window.py')},
               scope='CPU miniature through the real chain transport and W0p canary code; the device canary/decode run in the chain itself')
    (O / 'evidence/transport-gate.json').write_text(json.dumps(row, indent=2) + '\n')
    print('transport gate PASS: W0p canary', rows['w0p_canary_k3x']['handovers'], 'handovers; old size refused; k3x decode identical')


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3,) * 2)
    main()
