"""CPU-only admission checks; no model allocations or device access."""
import json
import hashlib
from pathlib import Path
import memory_plan
import memory_gate

def census(n):
    return {'totals': {'device': n}, 'allocations': [
        {'live': True, 'memory': 'device', 'bytes': n}]}

def source_pins():
    root = Path(__file__).parent
    names = ('memory_plan.py', 'memory_gate.py', 'test_memory_plan.py',
             'strict_snapshot.hpp', 'rank.hpp', 'mtp.hpp', 'main.cpp',
             'p39_plan.hpp', 'p39_submit.hpp')
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in names}

def main():
    sources = source_pins()
    ledger = memory_plan.plan()
    ledger_path = Path(__file__).with_name('memory-plan.json')
    assert json.loads(ledger_path.read_text()) == ledger, 'stored memory ledger differs from generator'
    passed = 0
    for draft_rank in (0, 1):
        for context in memory_plan.CONTEXTS:
            for rank in (0, 1):
                row = ledger['placements'][str(draft_rank)]['capacities'][str(context)]['ranks'][rank]
                for mtp in (False, True):
                    limit = row['total_with_mtp_bytes'] if mtp else row['target_total_bytes']
                    assert memory_gate.check(census(limit), ledger, rank, mtp, context, draft_rank)['passed']
                    passed += 1
                    try:
                        memory_gate.check(census(limit + 1), ledger, rank, mtp, context, draft_rank)
                    except ValueError:
                        passed += 1
                    else:
                        raise AssertionError('over-limit admitted')
    for context in (255, 4095, 32769):
        try:
            memory_gate.check(census(1), ledger, 0, True, context, 0)
        except ValueError:
            passed += 1
        else:
            raise AssertionError('invalid context admitted')
    for draft_rank in (-1, 2):
        try:
            memory_gate.check(census(1), ledger, 0, True, 256, draft_rank)
        except ValueError:
            passed += 1
        else:
            raise AssertionError('invalid placement admitted')
    for placement in ledger['placements'].values():
        for capacity in placement['capacities'].values():
            for row in capacity['ranks']:
                assert row['allocation_margin_passed']
                passed += 1
    receipt = dict(schema='packet45.cpu-memory-gates.v1', passed=True,
        gate_count=passed, admission_successes=24, one_byte_over_plan_rejections=24,
        unsupported_context_rejections=3, invalid_draft_rank_rejections=2,
        margin_checks=12, device_executed=False,
        source_sha256=sources,
        memory_plan_json_sha256=hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        scope='CPU allocation arithmetic and admission only; no device discovery, allocations, residency, or timing measurements')
    assert source_pins() == sources, 'source changed during memory gates'
    Path(__file__).with_name('memory-plan-gates.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))

if __name__ == '__main__':
    main()
