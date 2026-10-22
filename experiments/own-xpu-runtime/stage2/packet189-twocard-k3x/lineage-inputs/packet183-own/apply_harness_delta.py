#!/usr/bin/env python3
"""Retarget the copied packet153 v5 harness from snapshot_host=static to S1.

Exact-once edits (refuses on a missing/ambiguous anchor, refuses to run twice):
  * one-load switch key snapshot_host -> dense_scales; variant static -> metadata;
  * lineage/static -> lineage/metadata; both selections carry 14 choices
    (snapshot_host stays "production" = bundle 8; dense_scales expanded|metadata);
  * configs static-{smoke,bracket}.json -> metadata-{smoke,bracket}.json;
  * job/unit/evidence names packet153/p153b -> packet183/p183;
  * the bracket summary gains an s1_decision block (min gain, record bar,
    chain rule) next to the unchanged packet153 candidate_qualified rule;
  * packet153's snapshot-only gates (state, real-shape, split, the static-table
    admission arithmetic) are removed; S1 gates replace them (qualify_cpu.py).
Writes harness-delta.patch (against packet153 after the identity rewrite).
"""
import difflib, json, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
V5 = HERE / 'v5'
SRC = HERE.parent / 'packet153-snapshot-host' / 'v5'
RECORD = 58.798108759182306


def once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'anchor count {n} in {what}: {old[:90]!r}')
    return text.replace(old, new, 1)


def orig(rel):
    p = SRC / rel.replace('p183_', 'p153_')
    return p.read_text().replace('packet153-snapshot-host', 'packet183-twocard-s1-micro').replace('p153_v5_', 'p183_v5_').replace('p153_ops_', 'p183_ops_') if p.exists() else ''


EDITS = {
 'bracket.py': [
  ("DOMAINS = {'snapshot_host': ('production','static')}", "DOMAINS = {'dense_scales': ('expanded','metadata')}"),
  ("read(views[0]['selection'])['choices']['snapshot_host']=='static'", "read(views[0]['selection'])['choices']['dense_scales']=='metadata'"),
 ],
 'bracket_config.py': [
  ('"""Fixed banked bundle8 plus one exact class-layout dimension."""', '"""Fixed banked bundle8 plus one exact kernel-only dimension: dense_scales (packet183 S1)."""'),
  ("VALUES=('static',)", "VALUES=('metadata',)"),
  ("reason='packet136 budget plus inherited probe scratch and 64 KiB immutable descriptor reserve on rank0'",
   "reason='packet136 budget plus inherited packet153 probe scratch and 64 KiB reserve (unused by S1: no new allocation)'"),
 ],
 'argument_gate.py': [
  ('def identity(kind,variant="static",lane="A"):', 'def identity(kind,variant="metadata",lane="A"):'),
  ('def probe(kind,check_limits=False,variant="static",lane="A"):', 'def probe(kind,check_limits=False,variant="metadata",lane="A"):'),
 ],
 'worker_gate.py': [
  ('def probe(kind,variant="static"):', 'def probe(kind,variant="metadata"):'),
  ("['choices']['snapshot_host']", "['choices']['dense_scales']"),
 ],
 'entry_gate.py': [
  ("unit='screen-packet153-'+variant+'-'+kind+'-'+lane+'.service'", "unit='screen-packet183-'+variant+'-'+kind+'-'+lane+'.service'"),
  ("group.replace('screen-packet153','wrong-packet153')", "group.replace('screen-packet183','wrong-packet183')"),
 ],
 'switch_gate.py': [
  ("for mode in ('production','static'):", "for mode in ('production','metadata'):"),
  ("b=out/'static.json'", "b=out/'metadata.json'"),
  ("sequence=['production','static','production','static','production']", "sequence=['production','metadata','production','metadata','production']"),
 ],
 'p183_v5_compare.py': [
  ("mode='production' if row['choice']=='control' else 'static')", "mode='expanded' if row['choice']=='control' else 'metadata')"),
  ("timing['mode']='production' if timing['choice']=='control' else 'static'", "timing['mode']='expanded' if timing['choice']=='control' else 'metadata'"),
  ("result['purpose']='one-load snapshot-host screen; fresh-load confirmation and full chain still required'",
   "result['purpose']='one-load S1 dense-scales screen (packet183); fresh-process record chain still required'"),
  ("    result['candidate_qualified']=drift<=3.0 and all(r['rate']>=1.02*max(controls) for r in rows if r['choice']=='candidate')\n    from analyze import analyze\n",
   "    result['candidate_qualified']=drift<=3.0 and all(r['rate']>=1.02*max(controls) for r in rows if r['choice']=='candidate')\n"
   "    cand=[r['rate'] for r in rows if r['choice']=='candidate']\n"
   "    if cand:\n"
   "        gain=min(cand)/max(controls)-1;bar=1.02*" + repr(RECORD) + "\n"
   "        result['s1_decision']=dict(min_gain_percent=100*gain,best_control_rate=max(controls),slower_candidate_rate=min(cand),\n"
   "            screen_winner=bool(drift<=3.0 and gain>=0.005),record_rate=" + repr(RECORD) + ",record_bar_rate=bar,\n"
   "            chain_rule_met=bool(result['candidate_qualified'] and min(cand)>=bar),\n"
   "            rule='screen winner: both candidates >= +0.5% over every control, drift <= 3%; chain: both >= +2% over every control AND >= 1.02 x 58.798109 (record); every view 13/13 exact and draft proposals identical (enforced above)')\n"
   "    from analyze import analyze\n"),
 ],
 'screen.py': [
  ("conditional_on='Exact packet153 smoke and its first-request data proof must pass before bracket'",
   "conditional_on='Exact packet183 metadata smoke and its first-request data proof must pass before bracket'"),
  ("smoke=load(HERE/'evidence/device-static-smoke-B-p153b')", "smoke=load(HERE/'evidence/device-metadata-smoke-B-p183')"),
  ("'packet153 smoke/data proof required'", "'packet183 smoke/data proof required'"),
 ],
 'readiness.py': [
  ("assert lane=='B' and variant=='static','registered lane-B probe only'", "assert lane=='B' and variant=='metadata','registered lane-B probe only'"),
 ],
 'analyze.py': [
  ("schema='packet153.snapshot-host.v1'", "schema='packet183.host-boundary.v1'"),
 ],
 'submission_rehearsal.py': [
  ("prefix='p153-submission-'", "prefix='p183-submission-'"),
  ("'historical chain accepted as packet153'", "'historical chain accepted as packet183'"),
  ("method='packet153 packet56_submission.prepare_submission'", "method='packet183 packet56_submission.prepare_submission'"),
  ("packet153_evidence_refused=refusal", "packet183_evidence_refused=refusal"),
  ("print('Own prepare_submission: historical136 replay PASS;153 refuses historical promotion')", "print('Own prepare_submission: historical136 replay PASS;183 refuses historical promotion')"),
 ],
 'cpu_seal.py': [
  ("GATES=('build','state','real-shape','admission','analysis','submission-rehearsal','controller','safety','exec-limits','loader','switch')",
   "GATES=('build','s1-bytes','real-census','full-shape','admission','analysis','submission-rehearsal','controller','safety','exec-limits','loader','switch','expected-gain')"),
  ("for mode in ('production','static') for n in", "for mode in ('production','metadata') for n in"),
  ("row=dict(schema='packet153.cpu-composition.v1'", "row=dict(schema='packet183.cpu-composition.v1'"),
  ("variants=['production','static']", "variants=['production','metadata']"),
  (" for mode in ('production','static'):save(", " for mode in ('production','metadata'):save("),
 ],
}
REMOVE = ['state_gate.py', 'real_shape_gate.py', 'split_cpu.py', 'native/state_bytes.cpp', 'native/split_bytes.cpp']


def selection(mode_value):
    path = V5 / 'lineage/production/selection.json'
    row = json.loads(path.read_text())
    assert 'dense_scales' not in row['choices'] and row['choices']['snapshot_host'] == 'production'
    row['choices']['dense_scales'] = mode_value
    assert len(row['choices']) == 14
    return json.dumps(row, indent=2) + '\n'


def main():
    if (V5 / 'lineage/metadata').exists():
        raise SystemExit('already applied')
    patches = []
    for rel, edits in EDITS.items():
        p = V5 / rel
        text = p.read_text()
        before = text
        for old, new in edits:
            text = once(text, old, new, rel)
        p.write_text(text)
        patches.append(''.join(difflib.unified_diff(orig(rel).splitlines(True), text.splitlines(True), 'packet153/v5/' + rel, 'packet183/v5/' + rel)))
        assert orig(rel) == before, 'copied harness differs from packet153: ' + rel
    # Lineage and configs.
    shutil.move(str(V5 / 'lineage/static'), str(V5 / 'lineage/metadata'))
    meta = selection('metadata')
    prod = selection('expanded')
    (V5 / 'lineage/production/selection.json').write_text(prod)
    (V5 / 'lineage/metadata/selection.json').write_text(meta)
    import hashlib
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for kind in ('smoke', 'bracket'):
        old = V5 / 'configs' / ('static-' + kind + '.json')
        cfg = json.loads(old.read_text())
        for view in cfg['views']:
            mode = 'metadata' if view['choice'] == 'candidate' else 'production'
            path = V5 / 'lineage' / mode / 'selection.json'
            view['selection'] = str(path)
            view['selection_sha256'] = sha(path)
        (V5 / 'configs' / ('metadata-' + kind + '.json')).write_text(json.dumps(cfg, indent=2) + '\n')
        old.unlink()
    for rel in REMOVE:
        p = V5 / rel
        patches.append(''.join(difflib.unified_diff(p.read_text().splitlines(True), [], 'packet153/v5/' + rel, '/dev/null')))
        p.unlink()
    (HERE / 'harness-delta.patch').write_text(''.join(patches))
    print('harness delta applied:', len(EDITS), 'files edited,', len(REMOVE), 'removed')


if __name__ == '__main__':
    main()
