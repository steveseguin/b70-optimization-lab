"""Offline timing localization; this does not claim a device flag's first writer."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent


def main():
    source = P / 'evidence/p58amd-original-incident/S1/incident-retrospective/demand-events.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    assert len(rows) == 48 and [r['layer'] for r in rows] == list(range(48))
    result = []
    for row in rows:
        events = {event['kind']: event for event in row['events']}
        assert not row['staged_entries'] and not row['staged_bytes']
        assert 'packed-H2D' not in events
        edges = [('router', 'descriptor'), ('descriptor', 'descriptor-D2H'),
                 ('stage-map-H2D', 'missing-gate'), ('missing-gate', 'resident-down'),
                 ('resident-down', 'missing-down')]
        ordered = {a + ' -> ' + b: events[a]['end_ns'] <= events[b]['start_ns']
                   for a, b in edges}
        assert all(ordered.values())
        result.append(dict(layer=row['layer'], ordered_edges=ordered,
                           durations_ns={k: e['end_ns'] - e['start_ns'] for k, e in events.items()}))
    manifest = P/'inputs/incident-retrospective/plan.tsv'
    exceptional = [dict(tensor=r[1], grid=int(r[3]), bytes_per_expert=int(r[5])//512)
                   for line in manifest.read_text().splitlines() if
                   (r := line.split())[2] == 'routed_experts' and
                   ('ffn_gate_exps' in r[1] or 'ffn_up_exps' in r[1]) and int(r[3]) != 22]
    assert len(exceptional) == 2 and all(r['tensor'].startswith('blk.2.') and r['grid']==21 for r in exceptional)
    report = dict(
        schema='packet58amd.incident-audit.v1', device_executed=False,
        source=str(source.relative_to(P)), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        packed_expert_copies=0, recorded_dependency_edges_ordered=True,
        observation='Layers 0–2 have substantial missing-kernel work; layers 3–47 take only a few microseconds.',
        inference='The transition into layer 3 is the first localization target; timestamps do not identify the flag writer.',
        manifest=str(manifest.relative_to(P)), manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        exceptional_banks=exceptional,
        dispatch_bug='IQ3_XXS layer 2 was unconditionally dispatched through the fixed IQ2_S gate/up kernel.',
        cause_identified=True, device_confirmation_pending=True, repair_qualified=False, layers=result)
    (P / 'evidence/p58amd-incident-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('48 layers audited; ordered recorded edges; mixed-layout dispatch defect at layer 2; device confirmation pending')


if __name__ == '__main__':
    main()
