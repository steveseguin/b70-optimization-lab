# Derived from scripts/check-four-card-health.py SHA256 1e4c1dabed0c176f3d26f3d038c582fcfa0c8b7a7d90eb910fb62c3fd592398b
#!/usr/bin/env python3
"""One bounded four-card health probe after a GPU fault (AGENTS.md, owner rule of 2026-10-03).

One process, each card once: a copy round trip, a small fp32 and bf16 GEMM checked against the CPU, a
host-staged card-to-card copy, and a look at the kernel journal for new fault lines during the probe.
Writes a receipt; exit 0 only if every card passes and the journal stayed clean.

    check-four-card-health.py <receipt.json>
"""
import datetime, hashlib, json, re, subprocess, sys, time
from pathlib import Path

FAULT = re.compile(r'Fault response|CAT error|engine reset|Engine reset|GPU HANG|GuC.*reset|coredump|Timedout job|wedged')
start = datetime.datetime.now(datetime.timezone.utc)
since = start.strftime('%Y-%m-%d %H:%M:%S UTC')
# Latest owner rule: a fault halts new GPU work; no recovery/retry loop.
initial_journal = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager'], text=True, timeout=20)
if FAULT.search(initial_journal):
    refusal = {'schema': 'ltx.four-card-health.v1', 'start_utc': since,
               'passed': False, 'device_count': 0, 'cards': [],
               'reason': 'Earlier boot fault; no GPU probe started',
               'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with Path(sys.argv[1]).open('x') as handle:
        json.dump(refusal, handle, indent=2)
    print(json.dumps(refusal)); sys.exit(2)
import torch  # noqa: E402

receipt = {'schema': 'ltx.four-card-health.v1', 'start_utc': since,
           'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
           'kernel': Path('/proc/sys/kernel/osrelease').read_text().strip(), 'torch': torch.__version__, 'cards': [],
           'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
ok = torch.xpu.is_available() and torch.xpu.device_count() == 4
receipt['device_count'] = torch.xpu.device_count() if torch.xpu.is_available() else 0
g = torch.Generator().manual_seed(7)
a = torch.randn(512, 768, generator=g); b = torch.randn(768, 640, generator=g)
ref = a @ b
prev = None
for i in range(receipt['device_count']):
    dev = torch.device(f'xpu:{i}'); row = {'device': str(dev), 'name': torch.xpu.get_device_name(i)}
    t0 = time.time()
    try:
        x = a.to(dev); y = b.to(dev)
        row['copy_roundtrip_exact'] = bool(torch.equal(x.cpu(), a))
        z = (x @ y).cpu()
        row['gemm_fp32_max_abs_err'] = float((z - ref).abs().max())
        zb = (x.to(torch.bfloat16) @ y.to(torch.bfloat16)).float().cpu()
        row['gemm_bf16_max_abs_err'] = float((zb - ref).abs().max())
        row['gemm_repeat_exact'] = bool(torch.equal(z, (x @ y).cpu()))
        if prev is not None:
            row['staged_from_previous_exact'] = bool(torch.equal(prev.cpu().to(dev).cpu(), a))
        prev = x
        torch.xpu.synchronize(dev)
        row['pass'] = (row['copy_roundtrip_exact'] and row['gemm_repeat_exact'] and row['gemm_fp32_max_abs_err'] < 1e-2
                       and row['gemm_bf16_max_abs_err'] < 5.0 and row.get('staged_from_previous_exact', True))
    except Exception as error:  # noqa: BLE001
        row['error'] = repr(error); row['pass'] = False
    row['seconds'] = round(time.time() - t0, 3)
    ok = ok and row['pass']
    receipt['cards'].append(row)
    # One card at a time; do not issue work to the next after a failure/fault.
    during = subprocess.check_output(['journalctl', '-k', '-b', '--since', since, '--no-pager'], text=True, timeout=20)
    if not row['pass'] or FAULT.search(during):
        ok = False
        break
time.sleep(3)
journal = subprocess.check_output(['journalctl', '-k', '-b', '--since', since, '--no-pager'], text=True, timeout=20)
receipt['journal_fault_lines_during_probe'] = [l for l in journal.splitlines() if FAULT.search(l)][:20]
whole = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager'], text=True, timeout=20)
receipt['fault_lines_earlier_this_boot'] = len([l for l in whole.splitlines() if FAULT.search(l)]) - len(receipt['journal_fault_lines_during_probe'])
receipt['end_utc'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
receipt['passed'] = bool(ok and not receipt['journal_fault_lines_during_probe'])
with Path(sys.argv[1]).open('x') as handle:
    handle.write(json.dumps(receipt, indent=1) + '\n')
print(json.dumps({k: receipt[k] for k in ('passed', 'device_count', 'fault_lines_earlier_this_boot', 'journal_fault_lines_during_probe')}))
for c in receipt['cards']:
    print(c)
sys.exit(0 if receipt['passed'] else 1)
