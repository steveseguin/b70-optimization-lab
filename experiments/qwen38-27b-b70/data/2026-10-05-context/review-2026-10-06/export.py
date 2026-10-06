"""Export compact review evidence from completed raw trials; no inference calls."""
import csv
import hashlib
import json
from pathlib import Path
import tomllib

RAW = Path('/mnt/fast-ai/bench-results')
OUT = Path(__file__).resolve().parent
SELECTION = [
    'context-planA-client',
    'context-clm-tenth-20261005/client/rd480',
    'context-clm-tenth-20261005/client/rd120',
    'context-clm-eleventh-20261005/client/rd120',
    'context-clm-fourteenth-20261005/client/rd120-d12',
    'context-clm-fourteenth-20261005/client/rd120-d6',
    'context-clm-fourteenth-20261005/client/rd120-base',
]


def source(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size}


def main():
    rows = []
    for parent in SELECTION:
        for summary in sorted((RAW / parent).rglob('*.summary.txt')):
            lines = summary.read_text().splitlines()
            metrics = next(csv.DictReader(lines[:2], delimiter='\t'))
            job = summary.parent / 'jobs' / summary.name.removesuffix('.summary.txt')
            for result in sorted(job.glob('*/result.json')):
                trial = result.parent
                details = trial / 'verifier/details.json'
                if not details.exists():
                    continue  # Interrupted trials are not measurements.
                config = trial / 'config.json'
                cfg = json.loads(config.read_text())
                task = Path(cfg['task']['path'])
                meta_path = task / 'task.toml'
                meta = tomllib.loads(meta_path.read_text())['metadata']
                grade = json.loads(details.read_text())
                sources = {'summary': source(summary), 'verifier': source(details),
                           'trial_result': source(result), 'trial_config': source(config),
                           'task': source(meta_path)}
                for key, rel in [('expected', 'tests/expected.json'), ('stream', 'environment/stream.jsonl'),
                                 ('grader', 'tests/grade.py'), ('reference', 'tests/reference.json')]:
                    p = task / rel
                    if p.exists():
                        sources[key] = source(p)
                row = {'id': str(trial.relative_to(RAW)), 'metrics': metrics, 'task_metadata': meta,
                       'grade': {key: grade[key] for key in ['n', 'correct', 'score', 'score_raw', 'void',
                                 'counts', 'violations', 'per_key'] if key in grade},
                       'agent': {'name': cfg['agent']['name'], 'model_name': cfg['agent']['model_name'],
                                 'kwargs': cfg['agent']['kwargs']}, 'sources': sources}
                rows.append(row)
                copied = OUT / 'records' / Path(parent).parts[0] / summary.parent.parent.name / trial.name
                copied.mkdir(parents=True, exist_ok=True)
                for p, name in [(summary, 'summary.tsv'), (details, 'verifier.json'),
                                (meta_path, 'task.toml'), (task / 'tests/expected.json', 'expected.json')]:
                    dest = copied / name
                    dest.write_bytes(p.read_bytes())
                    row.setdefault('copies', {})[name] = str(dest.relative_to(OUT))
    payload = {'schema': 'context-review-evidence.v1', 'review_date': '2026-10-06',
               'scope': 'Completed selected trials, including invalid attempts. Raw sources unchanged. '
                        'Scores from verifier/details.json; timing and token counts from saved summary TSV. '
                        'Source hashes bind originals; copies permit score and summary review without the originating host. '
                        'These files are not a complete inference-runtime reproduction package.',
               'rows': rows}
    (OUT / 'evidence.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(f'Exported {len(rows)} completed trial records')
    for r in rows:
        m,g = r['metrics'],r['grade']
        print(r['id'], f"{g['correct']}/{g['n']}", 'VOID' if g['void'] else 'valid', m['wall_s'])


if __name__ == '__main__':
    main()
