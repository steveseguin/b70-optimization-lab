#!/usr/bin/env python3
"""Recompute packet58-onecard-cache23-chain readiness immediately before launch (CPU only; never launches).

Runs the packet's generated verify_ready.py (seal, composition, chain flags, submission pins, fresh output, bracket digests,
same-boot check, chain-flags gate), then checks the final READY-FOR-DEVICE.json against the live state: final_checks digest,
chain command digest, engine bytes, capacity selection, host floor, every CPU gate receipt, fresh output and fault review.
Prints the ready row as JSON; non-zero exit on any difference. launch_chain.sh calls it.
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
X = ROOT / 'experiments/own-xpu-runtime'
O = X / 'ops/packet58c23chain-orchestration'
P = X / 'stage2/packet58-onecard-cache23-chain'
DEVICE = '083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a'
HOST_FLOOR = 100487123456
sys.path.insert(0, str(O))
import cpu_gates  # noqa: E402


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(ok, why):
    if not ok:
        raise ValueError(why)


def packet_ready():
    cp = subprocess.run([sys.executable, '-B', str(P / 'verify_ready.py'), '--output', str(P / 'ready.json')], cwd=ROOT, stdin=subprocess.DEVNULL,
                        capture_output=True, text=True, timeout=600, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    require(cp.returncode == 0, 'packet verify_ready refused: ' + (cp.stdout + cp.stderr)[-1200:])
    row = json.loads((P / 'ready.json').read_text())
    require(row['ready'] is True and row['passed'] is True and row['device_executed'] is False, 'ready.json not ready')
    return row


def evaluate(final=True):
    row = packet_ready()
    derived = json.loads((P / 'derived-chain.json').read_text())
    require(row['chain_command'] == derived['chain_command'], 'chain command differs from derived-chain.json')
    digest = hashlib.sha256(row['chain_command'].encode()).hexdigest()
    sel = json.loads((P / 'runtime-selection.json').read_text())
    require(sel['cache_cap'] == 'max23' and sel['cache_allocation_bytes'] == sel['cache_bytes'] == 23049601024 and sel['chain_flags'] == derived['flags'], 'capacity selection differs')
    require(sha(P / 'build/device/own-rt-iq3') == DEVICE, 'engine bytes differ from 083e3853')
    binding = json.loads((P / 'engine-binding.json').read_text())
    require(binding['engine']['sha256'] == DEVICE and binding['compiled_here'] is False, 'engine binding differs')
    ok, gates = cpu_gates.check()
    require(ok, 'a CPU gate receipt is missing or failed: ' + json.dumps({k: v['passed'] for k, v in gates.items()}))
    adm = json.loads((P / 'evidence/admission-gate.json').read_text())
    require(adm['recomputed']['screen_winner'] is True and adm['recomputed']['chain_rule'] is False and adm['admission']['record_bar']['tok_s'] == 35.92672010504166
            and adm['admission']['record_bar']['reference_submission'] == 'cmvjejvoi03qcrf0138emu5a6', 'admission gate facts differ')
    queue = json.loads((P / 'evidence/queue-gate.json').read_text())
    require(queue['plan']['host_required_available_bytes'] == HOST_FLOOR, 'queue plan host floor differs')
    require(not (ROOT / derived['chain_output']).exists() and not (P / 'evidence/fault-review-cache23-a.json').exists(), 'chain output or fault review not fresh')
    ledger = json.loads((ROOT / 'scripts/packet58_onecard_record_threshold.json').read_text())['records'][-1]
    require(ledger['reference_submission'] == 'cmvjejvoi03qcrf0138emu5a6' and ledger['threshold_tok_s'] == 35.92672010504166, 'live ledger moved; re-derive the bars')
    out = dict(schema='packet58cache23chain.verify-ready.v1', ready=True, device_executed=False, chain_command=row['chain_command'], chain_command_digest_sha256=digest,
               unit=derived['unit'], chain_output=derived['chain_output'], engine_sha256=DEVICE, capacity=dict(cache_cap='max23', cache_bytes=23049601024),
               host_required_available_bytes=HOST_FLOOR, launcher_floor_bytes=HOST_FLOOR + 1073741824, bracket=derived['bracket'], gates={k: v['sha256'] for k, v in gates.items()},
               packet_ready=dict(build_receipt_sha256=row['build_receipt_sha256'], submission_pins_sha256=row['submission_pins_sha256'], boot_id=row['boot_id']))
    if final:
        ready = json.loads((P / 'READY-FOR-DEVICE.json').read_text())
        require(ready['ready_for_device_chain'] is True and ready['passed'] is True and ready['chain_command_digest_sha256'] == digest
                and ready['chain_binary_sha256'] == DEVICE and ready.get('last_packet_write') is True, 'READY differs from the live state')
        require(ready['final_checks_sha256'] == sha(P / 'evidence/final-checks.json'), 'final-checks receipt differs from READY')
        require(sha(O / 'READY-FOR-DEVICE.json') == sha(P / 'READY-FOR-DEVICE.json'), 'ops and packet READY differ')
        out['ready_sha256'] = sha(P / 'READY-FOR-DEVICE.json')
    return out


def main():
    final = '--pre-ready' not in sys.argv
    try:
        out = evaluate(final)
    except (ValueError, KeyError, OSError, AssertionError) as e:
        print(json.dumps(dict(ready=False, reason=str(e)[:800]), indent=2))
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
