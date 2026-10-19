"""Verify retained data and numerical summaries without reading model weights."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import statistics as st
from audit import P, ROOT, guard


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    guard()
    preparation = json.loads((P/'evidence/preparation.json').read_text())
    positions = json.loads((P/'evidence/positions.json').read_text())
    raw = gzip.decompress((P/'evidence/hidden.bf16.gz').read_bytes())
    assert sha(raw)==preparation['hidden_sha256'] and len(raw)==385*2560*2
    assert len(positions)==385
    assert sum(r['corpus']=='suite' for r in positions)==200
    assert sum(r['corpus']=='independent' for r in positions)==120
    assert sum(r['head']=='draft' for r in positions)==65
    fractions = list(csv.DictReader((P/'evidence/fractions.csv').open()))
    assert len(fractions)==385*5
    analysis = json.loads((P/'evidence/analysis.json').read_text())
    for row in analysis['summaries']:
        group = [r for r in fractions if r['corpus']==row['corpus'] and r['scheme']==row['scheme']]
        values = [float(r['read_equivalent_fraction']) for r in group]
        assert len(group)==row['positions'] and all(0<=v<=1 for v in values)
        assert abs(st.mean(values)-row['mean'])<1e-14
        assert min(values)==row['minimum'] and max(values)==row['maximum']
        assert st.median(values)==row['median']
    for r in fractions:
        if r['head']=='target':
            merged = (float(r['target_prefix_read_fraction'])*202240+float(r['target_suffix_read_fraction'])*46080)/248320
            assert abs(merged-float(r['read_equivalent_fraction']))<1e-14
    pricing = json.loads((P/'evidence/pricing.json').read_text())
    assert pricing['intervals']==1188 and abs(pricing['record_tok_s']-58.798108759182306)<1e-10
    assert max(r['gain_percent'] for r in pricing['results'])<3
    for path, digest in pricing['source_pins'].items():
        assert sha(Path(path).read_bytes())==digest
    reads = analysis['weight_reads']
    assert sum(r['count'] for r in reads)==248320
    assert all(a['start']+a['count']==b['start'] for a,b in zip(reads,reads[1:]))
    assert sum(r['bytes'] for r in reads)==521472000
    assert preparation['target_top5_exact_checks']==1600 and preparation['draft_winner_checks']==65
    probe = json.loads((P/'evidence/draft-probe-idle/receipt.json').read_text())
    assert not probe['passed'] and probe['error']=='std::bad_alloc'
    assert all(t['backend']=='MockDevice' and t['live_bytes']==0 and t['safe_to_exit'] for t in probe['teardown'])
    assert not (P/'READY').exists() and not (P/'briefs/build.md').exists()
    report = dict(passed=True, positions=385, target_positions=320, native_draft_positions=65,
                  requested_draft_coverage_complete=False, full_head_rows=248320,
                  fractions=len(fractions), exact_saved_logit_checks=1665,
                  record_intervals=1188, native_probe_drained=True,
                  root_free_bytes=shutil.disk_usage(ROOT).free,
                  retained_files={str(p.relative_to(P)):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
                                  for p in sorted((P/'evidence').rglob('*')) if p.is_file() and p.name!='verification.json'})
    (P/'evidence/verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='retained_files'}))


if __name__=='__main__':
    main()
