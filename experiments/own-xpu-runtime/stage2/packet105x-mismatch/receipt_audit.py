"""Read retained p105 receipts only. No runtime or device imports."""
import gzip
import hashlib
import json
from pathlib import Path
import struct

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
EVIDENCE = P.parent / 'screen/v4-lanes/evidence'
FAILED = EVIDENCE / 'p105-71fdf43fef81-A-grid-1-head-split-compute'
CONTROL = EVIDENCE / 'p105-71fdf43fef81-A-grid-0-production'
SMOKE = EVIDENCE / 'p105s-B-head-split-compute-incident64-v1'
PREFIX = 202240


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    inputs = {}

    def read(path):
        data = path.read_bytes()
        inputs[str(path.relative_to(ROOT))] = sha(data)
        if path.suffix == '.gz':
            data = gzip.decompress(data)
        return json.loads(data)

    manifest = read(FAILED / 'suite-manifest.snapshot.json')
    source_packet = P.parent / 'packet105-head-split'
    build = read(source_packet / 'build-device-receipt.json')
    source_checks = {}
    for name in ('p105_runtime.hpp', 'request_reset.hpp', 'round2_submit.cpp',
                 'p105_submit.cpp', 'p105_common.hpp', 'owner.cpp', 'single_device.cpp',
                 'main.cpp', 'p33_submit.cpp'):
        path = source_packet / name
        key = str(path.relative_to(ROOT))
        digest = sha(path.read_bytes())
        assert build['sources'][key] == digest, 'source differs from compiled receipt: ' + name
        source_checks[key] = digest
    actual = read(FAILED / 'run/ranks/native-result.json')
    expected = None
    census = []
    for entry in manifest['prompts']:
        oracle = ROOT / entry['oracle_directory']
        receipt = read(oracle / 'receipt.json')
        assert inputs[str((oracle / 'receipt.json').relative_to(ROOT))] == entry['oracle_receipt_sha256']
        result = read(oracle / 'result.json')
        tokens = result['tokens']
        winners = [dict(generated_index=i+1, token=t) for i, t in enumerate(tokens) if t >= PREFIX]
        census.append(dict(prompt_id=entry['prompt_id'], tokens=len(tokens), suffix_winners=winners))
        if entry['prompt_id'] == 'architecture-tradeoff':
            expected = result
    assert expected is not None
    mismatches = [i for i, (a, b) in enumerate(zip(expected['tokens'], actual['tokens'])) if a != b]
    first = mismatches[0]
    assert (first, expected['tokens'][first], actual['tokens'][first]) == (30, 215495, 440)
    control = read(CONTROL / 'run/architecture-tradeoff/receipt.json')
    assert control['passed'] and control['tokens'] == expected['tokens']
    smoke = read(SMOKE / 'run/incident64/receipt.json')
    assert all(t < PREFIX for t in smoke['tokens'])
    states = []
    hidden_entries = []
    for label, base in [('failure', FAILED), ('smoke', SMOKE)]:
        for f in sorted(base.glob('run/*/state-evidence.json.gz')):
            state = read(f)
            for entry in state['files']:
                if entry['path'] == 'rank0/request-state-inventory.json':
                    inventory = json.loads(entry['text'])['standalone_target_mutable']
                    small = {k: v for k, v in inventory.items()
                             if k in ('card0:p105:active', 'card0:p105:index',
                                      'card0:p105:error', 'card0:p105:best16')}
                    states.append(dict(run=label, completed_request=f.parent.name, values=small))
                if 'final.mix' in entry['path'] or 'logits' in entry['path']:
                    hidden_entries.append(dict(run=label, completed_request=f.parent.name,
                                               path=entry['path'], bytes=entry['bytes'],
                                               sha256=entry['sha256'], retained_payload='text' in entry))
    zero, one = (sha(struct.pack('<I', v)) for v in (0, 1))
    for state in states:
        initial = state['completed_request'] == 'ranks'
        assert state['values']['card0:p105:active']['sha256'] == (one if initial else zero)
        assert state['values']['card0:p105:index']['sha256'] == zero
    assert not any(x['retained_payload'] for x in hidden_entries)
    assert not (FAILED / 'run/architecture-tradeoff/receipt.json').exists()
    oracle_dir = ROOT / next(e['oracle_directory'] for e in manifest['prompts']
                            if e['prompt_id'] == 'architecture-tradeoff')
    assert not (oracle_dir / 'step31').exists()
    result = dict(
        schema='packet105x.receipt-audit.v1', passed=True, device_executed=False,
        diagnosis='request reset zeros private suffix active without reinitializing it',
        first_mismatch=dict(zero_based_index=first, generated_index=first+1,
                            prompt_tokens=expected['prompt_tokens'],
                            absolute_input_position=expected['prompt_tokens']-1+first,
                            expected_token=expected['tokens'][first], expected_partition='rank0 suffix',
                            expected_local_suffix_index=expected['tokens'][first]-PREFIX,
                            produced_token=actual['tokens'][first], produced_partition='rank1 prefix',
                            matching_prefix_tokens=first,
                            rank_trace=[t for t in actual['rank_trace'] if t['fixture']==first+1]),
        expected_tokens=expected['tokens'], produced_tokens=actual['tokens'],
        production_control_exact=True, suite_suffix_winner_census=census,
        smoke=dict(tokens=len(smoke['tokens']), all_winners_in_prefix=True),
        known_u32_hashes=dict(zero=zero, one=one), state_inventory_extracts=states,
        hidden_payload_audit=hidden_entries,
        first_mismatch_hidden_retained=False, oracle_step31_retained=False,
        head_logit_recompute_performed=False,
        failure=read(FAILED / 'run/failure.json'),
        identity=read(FAILED / 'identity.json'),
        compiled_source_hashes_verified=source_checks,
        sources=inputs,
        audit_script_sha256=sha(Path(__file__).read_bytes()))
    (P / 'receipt-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: token 31, 215495 -> 440; post-reset private active=0; only suite suffix winner')


if __name__ == '__main__':
    main()
