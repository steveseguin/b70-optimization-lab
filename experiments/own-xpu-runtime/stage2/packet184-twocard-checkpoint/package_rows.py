#!/usr/bin/env python3
"""Packet184 seal + proposal (CPU only). Never queues, never launches, never touches PAUSE files.

Order (memory lessons "plan after seal", "first smokes fail on packaging"): CPU gates ->
package_rows (this) -> check_queue_rows (private-copy plan, rehearsal, pin guard on the sealed state)
-> final_checks -> final_checks --ready (READY-FOR-DEVICE.json last).

  1. record_harness_delta.py           lineage/harness-delta.{patch,json}
  2. stage the packet mirror            proposals/proposed-p184-two-card-B.txt
  3. v5/cpu_seal.py --seal             seal the source/build/gate closure (includes the mirror)
  4. copy the mirror to ops/lane-queue/proposed-p184-two-card-B.txt (PROPOSAL ONLY)
  5. v5/evidence/package-rows.json     seal and proposal digests
Run from the repository root: nice -n 19 taskset -c 8-15,24-31 python3 -B <this> </dev/null
"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V5 = HERE / 'v5'
NAME = 'proposed-p184-two-card-B.txt'
LIVE = HERE.parents[1] / 'ops/lane-queue' / NAME
MIRROR = HERE / 'proposals' / NAME
HOST = 97 * 1024**3 + 1200 * 1024**2          # 105,411,248,128 B: the bundle-8 v5 screen's tp2 admission
KINDS = dict(
    smoke=dict(expected=[240, 480], writes=1_000_000_000, legs=2,
               what='leg1: P x (K+M) uninterrupted reference (oracle-128 anchor) then P x K + save S1; leg2 (fresh pair): restore S1 + resume M'),
    lifecycle=dict(expected=[360, 780], writes=1_500_000_000, legs=3,
                   what='leg1: P x K + save S1, NEW one-shot x (M+R), NEW one-shot x M + save SREF; leg2: restore S1 + append T + M + save S2; '
                        'leg3: restore S2 + resume R, then (same pair) restore S1 + append T + M + save S2b; tools: inspect x6, delete S2b'))
HEADER = '''# PROPOSAL ONLY (packet184). Never queued by preparation; the device-window driver decides.
# Two-card (TP2) session checkpoints on the bundle-8 record line (packet136 parent objects relinked unchanged; entry TU
# recompiled with the checkpoint delta). Label experimental-two-card, contract v1.2+p184: NOT qualified until these rows pass.
# Lane B = cards 2+3 (PCI 0000:43:00.0 + 0000:47:00.0), two-card resident, whole host: PAUSE-A stays during both rows.
# The owner's endpoints on those cards (qwen38-27b-vision :18100 cards 1+2, qwen38-27b-fp8-tp1-test :18131 card 3) must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue; card 2 has a
# recorded GuC lockup history (CURRENT.md host notes) - the operator may instead run the same rows on lane A (cards 0+1).
# Host admission 105,411,248,128 B (97 GiB + 1200 MiB, the bundle-8 v5 screen's) plus the queue's 1 GiB at START; the
# 2026-10-22 windows measured MemAvailable 120.6-120.7 GB with endpoints stopped. Root free >= 25 GB + planned writes.
# P = incident-retrospective (87 tokens), K=256 (save at N=342), M=128, T = packet180's 126-token turn, R=64.
# Row 1 smoke: 2 fresh rank pairs. Gates: reference oracle-128; save run == reference[0:K]; merged K+M == reference; merged
#   draft guesses == reference; restore record; inspect. Expected 240-480 s (2 loads of 71-174 s, packet183 lane-B windows
#   2026-10-22); watchdog 3600 s; planned writes 1.0 GB.
# Row 2 lifecycle (depends on the smoke): 3 fresh rank pairs. Gates: append == one-shot; append + resume == one-shot;
#   warm repeat == append; S2 blobs == SREF blobs and S2b == S2 (both ranks, every saved buffer); lineage; delete.
#   Expected 360-780 s (3 loads); watchdog 3600 s; planned writes 1.5 GB.
# Expected seconds are informational; any gate failure is a FAILURE with the first failing gate in run/summary.json.
'''


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p):
    return str(Path(p).relative_to(ROOT))


def proposal(kind):
    k = KINDS[kind]
    row = dict(
        name=f'packet184-tp2-{kind}-B', lane='B',
        argv=['/usr/bin/python3', '-B', rel(V5 / 'checkpoint_job.py'), '--kind', kind, '--lane', 'B',
              '--output', str(V5 / 'evidence' / f'device-{kind}-B-p184'), '--fault-review', '{REVIEW}', '--authorized-device-window'],
        env_extra={}, review=rel(V5 / 'fault_review.py'),
        plan=dict(
            entry_rehearsal=dict(
                binaries=[dict(path=rel(V5 / 'build/gnu-host/own-rt-iq3'), sha256=sha(V5 / 'build/gnu-host/own-rt-iq3'),
                               args=['--checkpoint-inspect-metadata', '/nonexistent-p184-entry-rehearsal'], returncode=1, contains='ownrt.checkpoint-inspect.v1'),
                          dict(path=rel(V5 / 'build/tool/own-rt-ckpt-tool'), sha256=sha(V5 / 'build/tool/own-rt-ckpt-tool'),
                               args=['--checkpoint-inspect-metadata', '/nonexistent-p184-entry-rehearsal'], returncode=1, contains='ownrt.checkpoint-inspect.v1')],
                kind='micro', report_contract='report-contract.json',
                device_binary_not_executed=dict(path=rel(V5 / 'build/device/own-rt-iq3'), sha256=sha(V5 / 'build/device/own-rt-iq3')),
                preparation_probe_note=('Production-shape rehearsal (v5/evidence/production-shape.json via v5/p184_checkpoint_shape.py): real v5 startup of '
                                        'both ranks with numerical device addresses and no payload, save at N=342, fresh-process restore (resume and append), '
                                        'one real half step; worker/report rehearsal with real two-rank host pairs: v5/evidence/worker-rehearsal.json')),
            host_required_available_bytes=HOST, expected_seconds=k['expected'], watchdog_seconds=3600,
            planned_writes=k['writes'], planned_write_bytes=k['writes'], legs=k['legs'], what=k['what'],
            label='experimental-two-card', contract='v1.2+p184'))
    if kind == 'lifecycle':
        row['depends_on'] = ['packet184-tp2-smoke-B']
    return row


def content():
    return HEADER + ''.join(json.dumps(proposal(k)) + '\n' for k in ('smoke', 'lifecycle'))


def step(*args):
    r = subprocess.run([sys.executable, '-B', *map(str, args)], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
    if r.returncode:
        sys.exit(f'{args[0]} failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r.stdout


def main():
    if (HERE / 'READY-FOR-DEVICE.json').exists():
        sys.exit('READY-FOR-DEVICE.json exists: withdraw it (rename to v5/evidence/withdrawn-ready-<ts>.json) before repackaging')
    step(HERE / 'record_harness_delta.py')
    MIRROR.parent.mkdir(exist_ok=True)
    for old in MIRROR.parent.glob('*.txt'):
        old.unlink()
    MIRROR.write_text(content())
    step(V5 / 'cpu_seal.py', '--seal')
    shutil.copyfile(MIRROR, LIVE)
    assert sha(LIVE) == sha(MIRROR)
    rows = [json.loads(l) for l in LIVE.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    receipt = dict(passed=True, device_executed=False, queued=False, live_queue_modified=False,
                   proposal=rel(LIVE), proposal_sha256=sha(LIVE), mirror=rel(MIRROR),
                   cpu_seal=rel(V5 / 'cpu-seal.json'), cpu_seal_sha256=sha(V5 / 'cpu-seal.json'),
                   rows=[dict(job=r['name'], lane=r['lane'], depends_on=r.get('depends_on', []), expected_seconds=r['plan']['expected_seconds'],
                              watchdog_seconds=r['plan']['watchdog_seconds'], host_required_available_bytes=r['plan']['host_required_available_bytes'],
                              planned_writes=r['plan']['planned_writes'], legs=r['plan']['legs']) for r in rows])
    (V5 / 'evidence/package-rows.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print('package_rows: sealed; proposal', rel(LIVE), sha(LIVE)[:16], 'rows', [r['name'] for r in rows])


if __name__ == '__main__':
    main()
