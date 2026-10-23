#!/usr/bin/env python3
"""Reseal packet58-onecard-cache23-chain after the cache23 delta and its CPU gates (CPU only; never launches).

Same closure rules as ops/onecard_chain_derive.py's seal: every top-level text file (except the receipts) and every
file of the copied directories (selections, frozen-inputs, host-admission, native, lineage, screen-reader) is a source;
the three binaries are the artifacts; the gates are the inherited parent gates, the generator's chain-flags /
pin-relocation receipts, the cache23 delta log and every cpu_gates.py receipt that exists. Then:
  pin relocation + pin audit (no pin may point into the parent packet; no cross-packet mutable pin),
  submission-pins.json, seal.py --verify, verify_ready.py --output ready.json.
Idempotent: run it after phase-a gates (the seal-reading gates need a current seal) and again after phase b.
"""
import datetime, json, os, subprocess, sys
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
X = ROOT / 'experiments/own-xpu-runtime'
O = X / 'ops/packet58c23chain-orchestration'
P = X / 'stage2/packet58-onecard-cache23-chain'
P0 = X / 'stage2/packet58aj-onecard-resident'
sys.path.insert(0, str(X / 'ops'))
sys.path.insert(0, str(X / 'ops/lane-queue'))
import onecard_chain_derive as G  # noqa: E402
import cpu_gates  # noqa: E402

EXCLUDED = {'build-receipt.json', 'submission-pins.json', 'ready.json', 'READY-FOR-DEVICE.json'}
CAPACITY = dict(cache_cap='max23', cache_allocation_bytes=23049601024, cache_bytes=23049601024)
WINDOW_NOTE = '''
## packet58-onecard-cache23-chain capacity (added by ops/packet58c23chain-orchestration/reseal.py)

Every model window runs the packet182c record argv with `--cache-cap max23 --cache-bytes 23049601024`
(one 23,049,601,024-byte arena, the whole arena usable) on the packet58-onecard-cache23 engine
083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a, under that packet's re-partitioned
device plan (bound 29,828,911,360; driver allowance 671,088,640; transient 784,567,808) and host admission
100,487,123,456 B (launcher floor + 1 GiB). The 30.5 GB native/supervisor DRM guard is unchanged.
Bars: fresh exact WS128 must exceed 35.92672010504166 tok/s (cmvjejvoi03qcrf0138emu5a6) and the live ledger.
Launch only through ops/packet58c23chain-orchestration/launch_chain.sh (--dry-run first); never a lane queue row.
'''


def rel(p):
    return str(Path(p).relative_to(ROOT))


def main():
    G.refuse((P / 'evidence/cache23-chain-delta.json').is_file(), 'apply the cache23 delta first')
    # derived-chain.json: capacity record (verify_ready reads flags/chain_command/chain_output/bracket only)
    derived = G.read(P / 'derived-chain.json')
    derived['capacity'] = dict(**CAPACITY, argv={'--cache-cap': 'max23', '--cache-bytes': '23049601024'}, engine_sha256=G.sha(P / 'build/device/own-rt-iq3'),
                               memory_plan='packet58-onecard-cache23 admission.json (apply_cache23_chain_delta.py)', host_required_available_bytes=100487123456,
                               applied_by='ops/packet58c23chain-orchestration/apply_cache23_chain_delta.py', delta_log='evidence/cache23-chain-delta.json')
    G.save(P / 'derived-chain.json', derived)
    if 'packet58-onecard-cache23-chain capacity' not in (P / 'WINDOW.md').read_text():
        G.put(P / 'WINDOW.md', (P / 'WINDOW.md').read_text().rstrip('\n') + '\n' + WINDOW_NOTE)
    # The generator's READY (written at derivation, before the cache23 delta) is retired to the derivation record; final_checks.py --ready
    # writes the final READY last. The packet copy was pin-relocated by an earlier reseal; the ops copy keeps the generator's bytes.
    for src, dst in ((O / 'READY-FOR-DEVICE.json', O / 'derivation-READY-FOR-DEVICE.json'), (P / 'READY-FOR-DEVICE.json', P / 'evidence/derivation-READY-FOR-DEVICE.json')):
        if src.is_file() and G.read(src).get('generator') == 'ops/onecard_chain_derive.py' and 'final_checks_sha256' not in G.read(src):
            G.refuse(not dst.exists(), f'{dst.name} already exists')
            os.replace(src, dst)
    receipt = G.read(P / 'build-receipt.json')
    files = [f for f in P.glob('*') if f.is_file() and f.suffix in G.TEXT and f.name not in EXCLUDED]
    for d in G.COPY_DIRS:
        files += [f for f in (P / d).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
    artifacts = {r: G.sha(P / r) for r in ('build/device/own-rt-iq3', 'build/device/p58-cache-fixtures', 'build/gnu-host/own-rt-iq3')}
    gates = dict(receipt['gates'])
    gates['evidence/cache23-chain-delta.json'] = None
    for name, leaf in cpu_gates.RECEIPTS.items():
        if (P / 'evidence' / leaf).is_file():
            gates['evidence/' + leaf] = None
    for name in gates:
        row = G.read(P / name)
        G.refuse(row.get('passed') is True and row.get('device_executed') is False, 'gate not passed: ' + name)
        gates[name] = G.sha(P / name)
    receipt.update(sources={rel(f): G.sha(f) for f in sorted(files)}, artifacts=artifacts, gates=gates, **CAPACITY,
                   native_recompiled=True,   # the bound engine differs from the parent harness engine (8bcb6d8c) and from packet182c's (1b41fb4d)
                   engine_binding_sha256=G.sha(P / 'engine-binding.json'), cache23_chain_delta_sha256=G.sha(P / 'evidence/cache23-chain-delta.json'),
                   qualification='packet58-onecard-cache23 screen winner (+1.72 %, fills -12.9 %, 60/60 exact, 2026-10-23) admitted as a chain by coordinator ruling '
                                 '(idle lanes); engine 083e3853 reused byte for byte; cache23 device plan; fresh WS128 must beat 35.926720.',
                   resealed_by='ops/packet58c23chain-orchestration/reseal.py', resealed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    G.save(P / 'build-receipt.json', receipt)
    gate_paths = [P / n for n in gates]
    late = G.relocate_pins(P, P0, ROOT, gate_paths)
    if late:
        receipt = G.read(P / 'build-receipt.json')
        receipt['reseal_pin_relocation'] = receipt.get('reseal_pin_relocation', []) + late
        G.save(P / 'build-receipt.json', receipt)
        # sources touched by the relocation are re-hashed
        receipt['sources'] = {rel(f): G.sha(f) for f in sorted(files)}
        receipt['gates'] = {n: G.sha(P / n) for n in gates}
        G.save(P / 'build-receipt.json', receipt)
    names = [n for n in ('packet58_submission.py', 'composition.py', 'submission_cli.py', 'shared_submission_cli.py', 'suite_metrics.py', 'submission-policy.json', 'record-threshold.snapshot') if (P / n).is_file()]
    G.save(P / 'submission-pins.json', dict(schema=f'{P.name}.submission-pins.v1', build_receipt_sha256=G.sha(P / 'build-receipt.json'),
                                            sources={rel(P / n): G.sha(P / n) for n in names}, artifacts=artifacts, finalized_before_chain=True))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for args in (['seal.py', '--verify'], ['verify_ready.py', '--output', str(P / 'ready.json')]):
        cp = subprocess.run([sys.executable, '-B', str(P / args[0]), *args[1:]], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, timeout=600)
        G.refuse(cp.returncode == 0, f'{args[0]} refused: ' + (cp.stdout + cp.stderr)[-1500:])
    ready = G.read(P / 'ready.json')
    G.refuse(ready['ready'] is True and ready['chain_command'] == derived['chain_command'], 'ready.json not ready')
    bad, manifests = G.pin_audit(P, ROOT, gate_paths, parent=P0)
    G.refuse(not bad, f'pin audit refused ({len(bad)}): ' + '; '.join(bad[:12]))
    row = dict(schema='packet58cache23chain.reseal.v1', passed=True, device_executed=False, sources=len(receipt['sources']), artifacts=artifacts, gates=sorted(gates),
               build_receipt_sha256=G.sha(P / 'build-receipt.json'), submission_pins_sha256=G.sha(P / 'submission-pins.json'), ready_sha256=G.sha(P / 'ready.json'),
               pin_audit=dict(passed=True, manifests=len(manifests), parent_pins=0, cross_packet_mutable=0, late_relocations=len(late)),
               utc=receipt['resealed_utc'])
    G.save(O / 'reseal.json', row)
    print(json.dumps(dict(passed=True, sources=row['sources'], gates=len(gates), manifests=len(manifests), build_receipt=row['build_receipt_sha256'][:16])))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except G.Refused as e:
        print('reseal: REFUSED ' + str(e), file=sys.stderr)
        raise SystemExit(2)
