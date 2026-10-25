"""Small independent retained-receipt audit; does not reread model/state arrays."""
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    here = Path(__file__).resolve().parent
    summary_path = here/'ring-pending-provider-proof/summary.json'
    summary = json.loads(summary_path.read_text())
    run = Path(summary['source_run'])
    native = run/'stage0/native'
    survival_path = native/'ring-provider-survival.jsonl'
    attestation_path = native/'state-2147483647.ring-state.json'
    attestation = json.loads(attestation_path.read_text())
    rows = [json.loads(line) for line in survival_path.read_text().splitlines()]
    result_path = run/'pending-ring-live-result.json'
    result = json.loads(result_path.read_text())
    assert result['passed'] is True and result['error'] is None
    assert not result['live_pids'] and result['returncodes'] == dict.fromkeys(('0','1','2','3'),0)
    assert result['lifecycle_result_sha256'] == digest(run/'result.json')
    assert result['plan_sha256'] == digest(run/'plan.json')
    assert summary['original_result']['sha256'] == digest(result_path)
    assert summary['original_plan']['sha256'] == result['plan_sha256']
    assert summary['output_tokens'] == len(result['output_ids']) == 32
    assert summary['input_rows'] == result['input_position'] == 118
    assert summary['provider_pairs'] == result['provider_pairs'] == result['provider_serial'] == 117
    assert summary['pending_borrows'] == attestation['provider_pending_borrows'] == {'1':1,'2':2}
    assert digest(survival_path) == attestation['provider_survival_receipt_sha256']
    assert len(rows) == summary['provider_survival_checks'] == 2
    checks = []
    for row, expected, abort in zip(rows, summary['survival_audit']['frontiers'], result['pending_provider']['aborts']):
        assert row['before_payload'] == row['after_payload']
        sha = hashlib.sha256(row['before_payload'].encode()).hexdigest()
        assert sha == row['before_payload_sha256'] == row['after_payload_sha256']
        payload = json.loads(row['before_payload'])
        allocations = payload['allocations']
        assert len(allocations) == len({item['id'] for item in allocations}) == 74
        assert sum(item['bytes'] for item in allocations) == row['comparison_bytes'] == 54862456
        assert row['canonical_allocations_checked'] == 73 and row['private_allocations_checked'] == 1
        assert all(row[key] is True for key in ('all_bytes_equal','host_equal','sequence_equal','prepared_bindings_equal'))
        assert payload['position'] == payload['provider_serial'] == expected['provider_position'] == abort['provider_serial']
        assert payload['host']['current']['extent'] == expected['current_extent']
        assert payload['host']['saved']['extent'] == expected['saved_extent']
        assert row['abort_sequence'] == expected['abort_sequence'] == abort['abort_sequence']
        assert row['discarded_row_ids'] == abort['discarded_rows']
        assert [v['row']['id'] for v in row['provider_at_capture']] == row['discarded_row_ids']
        assert row['provider_at_capture'][0]['row'] == row['oldest']
        assert row['actual_position'] == row['committed_position'] == row['oldest']['position']
        assert row['pending_tickets'] == 0
        advanced = all(payload['position'] > v['position'] and payload['provider_serial'] > v['serial']
                       for v in row['provider_at_capture'])
        assert advanced and row['provider_advanced_since_snapshot'] is True
        checks.append(dict(sequence=row['abort_sequence'], provider_position=payload['position'],
            captured_positions=[v['position'] for v in row['provider_at_capture']],
            discarded=row['discarded_row_ids'], compared_bytes=row['comparison_bytes'], payload_sha256=sha))
    assert sum(len(row['discarded_row_ids']) for row in rows) == summary['provider_survival_discarded_rows'] == 3
    assert summary['raw_bytes'] == sum(v['bytes'] for v in summary['raw_bundles']) == 444751114
    assert summary['recursive_proposals_consumed'] is False and summary['speed_claim'] is False
    inputs = [summary_path, survival_path, attestation_path, result_path, run/'result.json', run/'plan.json', Path(__file__)]
    print(json.dumps(dict(schema='ownrt.pending-provider-independent-receipt-review.v1', passed=True,
        checks=checks, inputs={str(p):digest(p) for p in inputs},
        scope='Independent terminal/summary/native survival receipt identities and full payload equality. Existing strict finalizer establishes raw target/draft parity; raw arrays were not reread by this small audit.'), indent=2))


if __name__ == '__main__':
    main()
