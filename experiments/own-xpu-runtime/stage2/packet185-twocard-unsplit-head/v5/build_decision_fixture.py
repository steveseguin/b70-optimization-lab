"""Freeze the REAL device streams the s185 decision is tested on (CPU-only, read-only sources).

1. packet183's lane-B one-load bracket (2026-10-22 12:03-12:11 UTC, bundle-8 line, all 13/13 exact):
   for each of its five views and twelve prompts, the request receipt reduced to the fields the
   packet85 interval model reads, plus rank 0's packet150 host scopes. Its controls are bundle 8
   with the split head, i.e. exactly packet185's `production` view.
2. packet106b's lane-B fresh-load v4 grid (2026-10-18, bundle-6 era): the only retained device
   evidence of the un-split target head (arms 0/3 `production`) next to the split head (arm 1),
   receipts reduced the same way (that harness recorded no packet150 scopes).
Sources are local untracked trees; every reduced file records its source path and sha256.
Writes only lineage-inputs/decision-fixtures/ (tracked, ~MB). Run once; refuses to overwrite.
"""
import gzip, hashlib, json, resource
from pathlib import Path
from p185_v5_build_engine import P, LOCAL, ROOT, sha, save, limits

OUT = LOCAL / 'lineage-inputs/decision-fixtures'
P183 = ROOT / 'experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/v5/evidence/device-metadata-v5-B-p183'
P106B = ROOT / 'experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence'
P106B_ARMS = {'p106b-13e3630d590c-B-grid-0-production': 'unsplit', 'p106b-13e3630d590c-B-grid-1-head-split': 'production',
              'p106b-13e3630d590c-B-grid-3-production': 'unsplit'}
KEYS = ('prompt_id', 'prompt_class', 'passed', 'exact_oracle', 'cached_tokens', 'prompt_tokens', 'token_timestamps',
        'generated_token_completion_timestamps', 'guess_rows')
TRACE = ('rank', 'op', 'token', 'position', 'fixture', 'speculative', 'busy_ms', 'sent', 'rank_received', 'rank_completed')


def reduce(path):
    r = json.loads(path.read_text())
    row = {k: r[k] for k in KEYS if k in r}
    row['rank_trace'] = [{k: t[k] for k in TRACE if k in t} for t in r['rank_trace'] if t['op'] in (1, 3, 9)]
    row['source'] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
    return row


def write(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(row, separators=(',', ':')).encode()
    path.write_bytes(gzip.compress(data, mtime=0))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    limits()
    if OUT.exists():
        raise SystemExit('decision fixtures exist; never overwritten')
    manifest = dict(schema='packet185.decision-fixtures.v1', device_executed=False, files={})
    summary = json.loads((P183 / 'bracket-summary.json').read_text())
    assert summary['passed'] and summary['all_13_exact'] and summary['draft_proposals_identical']
    manifest['packet183_bracket_summary_sha256'] = sha(P183 / 'bracket-summary.json')
    for view in sorted((P183 / 'run/views').iterdir()):
        for prompt in sorted(p for p in view.iterdir() if (p / 'receipt.json').exists() and p.name != 'incident64'):
            rel = f'packet183-v5/{view.name}/{prompt.name}'
            manifest['files'][rel + '/receipt.json.gz'] = write(OUT / rel / 'receipt.json.gz', reduce(prompt / 'receipt.json'))
            timings = prompt / 'rank0/timings.jsonl'
            scopes = [json.loads(x) for x in timings.read_text().splitlines() if x.strip() and 'p150_segment' in x]
            manifest['files'][rel + '/rank0-scopes.json.gz'] = write(OUT / rel / 'rank0-scopes.json.gz',
                dict(source=dict(path=str(timings.relative_to(ROOT)), sha256=sha(timings)), records=scopes))
    for arm, variant in P106B_ARMS.items():
        run = P106B / arm / 'run'
        for receipt in sorted(run.glob('*/receipt.json')):
            r = json.loads(receipt.read_text())
            if 'prompt_class' not in r:
                continue
            rel = f'packet106b-v4/{arm}/{receipt.parent.name}'
            manifest['files'][rel + '/receipt.json.gz'] = write(OUT / rel / 'receipt.json.gz', dict(reduce(receipt), variant=variant))
    save(OUT / 'manifest.json', manifest)
    print('fixtures', len(manifest['files']), 'bytes', sum(f.stat().st_size for f in OUT.rglob('*') if f.is_file()))


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    main()
