#!/usr/bin/env python3
"""Frozen lexical retrieval evaluation; expected evidence never enters search."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('navigator', ROOT / 'tools/lab_navigator.py')
nav = importlib.util.module_from_spec(spec); spec.loader.exec_module(nav)
p = argparse.ArgumentParser(); p.add_argument('--index', required=True); p.add_argument('--split', choices=['development','heldout'], required=True); p.add_argument('--out', required=True)
a = p.parse_args()
source = Path(__file__).parent / 'evaluation/queries.json'
packet = json.loads(source.read_text())
rows=[]
for case in packet['queries']:
    if case['split'] != a.split: continue
    result = nav.search(a.index, case['query'], 8)
    assert result['commit'] == packet['source_commit']
    spans=[]
    for expected in case['expected_evidence']:
        relevant = [h for h in result['hits'] if h['path']==expected['path'] and h['blob']==expected['git_blob_oid']]
        covered = {n for h in relevant for n in range(h['start_line'],h['end_line']+1)}
        wanted = set(range(expected['start_line'],expected['end_line']+1))
        spans.append({'path':expected['path'], 'start_line':expected['start_line'], 'end_line':expected['end_line'], 'covered':wanted<=covered, 'line_coverage':len(wanted&covered)/len(wanted)})
    expected_paths={e['path'] for e in case['expected_evidence']}
    ranks=[i+1 for i,h in enumerate(result['hits']) if h['path'] in expected_paths]
    rows.append({'id':case['id'], 'all_spans_covered':all(s['covered'] for s in spans), 'spans':spans, 'file_recall':len(expected_paths&{h['path'] for h in result['hits']})/len(expected_paths), 'first_relevant_rank':min(ranks, default=None), 'evidence_bytes':sum(len(h['text'].encode()) for h in result['hits']), 'retrieval':result})
spans=[s for r in rows for s in r['spans']]
report={'schema':'lab.navigator.evaluation.v1','split':a.split,'queries_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'navigator_sha256':hashlib.sha256((ROOT/'tools/lab_navigator.py').read_bytes()).hexdigest(),'index_sha256':hashlib.sha256(Path(a.index).read_bytes()).hexdigest(),'model_calls':0,'questions':len(rows),'all_spans_covered':sum(r['all_spans_covered'] for r in rows),'spans_covered':sum(s['covered'] for s in spans),'spans_total':len(spans),'rows':rows}
nav.write_json_new(a.out,report)
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
for r in rows: print(r['id'],r['all_spans_covered'],r['file_recall'],r['first_relevant_rank'],[(s['path'],round(s['line_coverage'],2)) for s in r['spans']])
