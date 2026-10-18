"""Summarize retained incident evidence; never open a model or device."""
import json
from build_engine import P, ROOT, sha, save


def main():
    run = P.parent / 'screen/quick/evidence/p69-quick-B-02-combined-a/run'
    rank = run / 'ranks/rank1'
    incident = run / 'incident64/rank1'
    read = lambda f: json.loads(f.read_text())
    rows = lambda f: [json.loads(line) for line in f.read_text().splitlines()]
    timings = rows(incident / 'timings.jsonl')
    draft = rows(incident / 'draft-rows.jsonl')
    allocation = next(r for r in read(rank / 'census.json')['allocations']
                      if r['label'] == 'card0:weight:output.weight')
    assert allocation['bytes'] == 248320 * 3380
    old = P / 'evidence/reseal-r3/previous'
    failed_cpu = (old / 'evidence/head-status/gnu-1.log').read_text()
    assert 'row=1 expected=42cc actual=fff7' in failed_cpu
    assert 'production argmax sticky error=1' in failed_cpu
    sources = [rank / 'receipt.json', rank / 'census.json', rank / 'reset-1.txt',
               incident / 'timings.jsonl', incident / 'draft-rows.jsonl',
               run / 'teardown.json', old / 'p69_head.cpp', old / 'p69_head.hpp',
               old / 'head_status_fixture.cpp', old / 'evidence/head-status/gnu-1.log']
    save(P / 'evidence/reseal-r3/diagnosis.json', dict(
        device_executed=False, sources={str(f.relative_to(ROOT)): sha(f) for f in sources},
        observed_rank_failure=read(rank / 'receipt.json')['error'],
        observed_target_completed_halves=len(timings), last_target_half=timings[-1],
        first_head_draft=next(r for r in draft if r.get('head')),
        resident_head_allocation=allocation, row_stride=3380, useful_row_read_bytes=3200,
        ignored_metadata_bytes_per_row=180,
        corrupting_kernel='p69::Head<64>::run/submit', corrupting_site='logits (target and draft)',
        sticky_writer='round2::simple_group<integrated::Op::argmax,1> at argmax',
        cpu_reproduction=failed_cpu,
        conclusion='Old row 1 starts in retained metadata, yields BF16 NaN 0xfff7; production argmax sets sticky error=1.',
        limitation='The device trace has no per-kernel error provenance. CPU reproduces the same failure mechanism; repaired device rerun pending.'))
    print('PASS: retained allocation and two-row CPU reproduction explain head/argmax failure')


if __name__ == '__main__':
    main()
