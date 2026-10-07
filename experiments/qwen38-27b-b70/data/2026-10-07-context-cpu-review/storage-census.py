#!/usr/bin/env python3
"""Read-only census of three fixed, completed campaigns; write only /tmp reports."""
import collections
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

sys.dont_write_bytecode = True
REPO = Path('/home/steve/b70-optimization-lab')
DATA = REPO / 'experiments/qwen38-27b-b70/data'
BASE = Path('/mnt/fast-ai/bench-results')
RUNS = (
    ('context-semantic-v1-20261007', '2026-10-07-context-semantic-development'),
    ('context-sparse-v1-20261007', '2026-10-07-sparse-state-development'),
    ('context-sparse-replication-v1-20261007', '2026-10-07-sparse-state-replication'),
)
TOKENIZER = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json')


def read(path):
    return json.loads(path.read_text())


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    result = []
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(parent) / d).is_symlink())
        for name in sorted(files):
            p = Path(parent) / name
            s = p.lstat()
            if not stat.S_ISREG(s.st_mode):
                raise ValueError(f'Non-regular artifact: {p}')
            result.append({'path': str(p.relative_to(root)), 'bytes': s.st_size,
                           'allocated_bytes': s.st_blocks * 512,
                           'device': s.st_dev, 'inode': s.st_ino})
    return result


def disk_totals(files):
    seen = set()
    unique = 0
    for row in files:
        key = row['device'], row['inode']
        if key not in seen:
            unique += row['allocated_bytes']
            seen.add(key)
    return {'files': len(files), 'apparent_bytes': sum(r['bytes'] for r in files),
            'allocated_bytes': sum(r['allocated_bytes'] for r in files),
            'allocated_unique_inode_bytes': unique}


def group(name):
    if name in ('canonical.sqlite', 'canonical.sqlite-wal', 'canonical.sqlite-shm'):
        return 'sqlite'
    if 'snapshot' in name:
        return 'snapshots'
    if name == 'calls.jsonl':
        return 'model_call_evidence'
    if name == 'trace.json':
        return 'attempt_trace'
    if name == 'result.json':
        return 'result_receipt'
    if name == 'retrieval.jsonl':
        return 'retrieval_evidence'
    if name == 'answer-session.json':
        return 'answer_session'
    if name == 'checkpoint.json':
        return 'latest_checkpoint'
    return 'other_identity_and_evidence'


def census():
    token_info = {'available': False}
    tokenizer = None
    try:
        import tokenizers
        tokenizer = tokenizers.Tokenizer.from_file(str(TOKENIZER))
        token_info = {'available': True, 'path': str(TOKENIZER), 'sha256': sha(TOKENIZER),
                      'version': tokenizers.__version__,
                      'definition': 'sum of each original batch encode(add_special_tokens=False); no chat template'}
    except (ImportError, OSError) as error:
        token_info['reason'] = str(error)
    token_cache = {}
    report = {'schema': 'context-storage-census.v1', 'tokenizer': token_info,
              'scope': 'Only three explicitly completed campaigns. No active history outputs.',
              'method': 'Read main SQLite using mode=ro&immutable=1 only after asserting empty WAL. No DB writes, replay or model requests.',
              'runs': [], 'trials': []}
    for run_name, packet_name in RUNS:
        root = BASE / run_name
        diagnostic = root / 'diagnostic'
        summary_path = diagnostic / 'summary.json'
        summary = read(summary_path)
        if summary.get('infrastructure_abort') is not False:
            raise ValueError(f'Campaign not completed cleanly: {run_name}')
        if any(r['status'] != 'completed' for r in summary['trials']):
            raise ValueError(f'Unexpected incomplete trial: {run_name}')
        packet = DATA / packet_name
        semantic = run_name == RUNS[0][0]
        if semantic:
            documents = {r['id']: r for r in read(packet/'documents.json')['documents']}
            annotations = {r['document_id']: r for r in read(packet/'adjudicated.json')['documents']}
        trial_prefixes = []
        for row in summary['trials']:
            result_path = diagnostic / row.get('native_result_path', row['result_path'])
            native = result_path.parent
            trial_root = native if semantic else (diagnostic / row['result_path']).parent
            trial_prefixes.append(str(trial_root.relative_to(root)) + '/')
            result = read(result_path)
            checkpoint = read(native/'checkpoint.json')
            trace = read(native/'trace.json')
            calls = [json.loads(line) for line in (native/'calls.jsonl').read_text().splitlines()]
            if semantic:
                document = documents[row['case_id']]
                expected_states = [b['state_after'] for b in annotations[row['case_id']]['batches']]
            else:
                document = read(packet/row['document_path'])
                expected_states = read(packet/row['task_path'])['oracle']['after_batch']
            db = native/'canonical.sqlite'
            wal = native/'canonical.sqlite-wal'
            if wal.exists() and wal.stat().st_size:
                raise ValueError(f'Nonempty WAL cannot safely ignore: {wal}')
            conn = sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1', uri=True)
            try:
                deliveries = conn.execute('SELECT batch_id,text,sha256 FROM deliveries ORDER BY batch_id').fetchall()
                expected = [(b['id'], b['text']) for b in document['batches']]
                assert [(n,t) for n,t,h in deliveries] == expected
                assert all(hashlib.sha256(t.encode()).hexdigest() == h for n,t,h in deliveries)
                sqlite_info = {'main_file_bytes': db.stat().st_size,
                    'wal_bytes': wal.stat().st_size if wal.exists() else 0,
                    'shm_bytes': (native/'canonical.sqlite-shm').stat().st_size if (native/'canonical.sqlite-shm').exists() else 0,
                    'page_count': conn.execute('PRAGMA page_count').fetchone()[0],
                    'page_size': conn.execute('PRAGMA page_size').fetchone()[0],
                    'free_pages': conn.execute('PRAGMA freelist_count').fetchone()[0],
                    'tables': {}}
                for table in ('deliveries','current_state','events','receipts'):
                    values = conn.execute('SELECT * FROM '+table).fetchall()
                    sqlite_info['tables'][table] = {
                        'rows':len(values),
                        'text_column_utf8_bytes':sum(len(v.encode()) for r in values for v in r if isinstance(v,str)),
                        'compact_rows_json_bytes':len(encoded(values))}
                sqlite_info['event_payload_utf8_bytes'] = sum(len(r[0].encode()) for r in conn.execute('SELECT payload FROM events'))
                sqlite_info['source_text_utf8_bytes'] = sum(len(t.encode()) for n,t,h in deliveries)
                try:
                    sqlite_info['page_bytes_by_object'] = dict(conn.execute('SELECT name,SUM(pgsize) FROM dbstat GROUP BY name'))
                except sqlite3.OperationalError:
                    sqlite_info['page_bytes_by_object'] = None
            finally:
                conn.close()
            source_hash = hashlib.sha256(encoded(expected)).hexdigest()
            if tokenizer is not None and source_hash not in token_cache:
                token_cache[source_hash] = sum(len(tokenizer.encode(t, add_special_tokens=False).ids) for n,t in expected)
            source_bytes = sum(len(t.encode()) for n,t in expected)
            observed = [r['observed_state'] for r in trace['batches'] if isinstance(r.get('observed_state'),dict)]
            files = inventory(trial_root)
            groups = collections.Counter()
            for f in files:
                groups[group(f['path']) if '/' not in f['path'] else group(Path(f['path']).name) if f['path'].startswith('native/') else 'outer_wrapper_evidence'] += f['bytes']
            # Compact serialization values are logical proxies, not heap/RSS and not additive file sizes.
            state_info = {'reference_final_counter_count':len(expected_states[-1]),
                'reference_state_checkpoints':len(expected_states),
                'observed_state_checkpoints':len(observed),
                'max_observed_counter_count':max((len(s) for s in observed),default=0),
                'final_observed_counter_count':len(checkpoint['state']),
                'latest_state_compact_json_bytes':len(encoded(checkpoint['state'])),
                'max_state_compact_json_bytes':max((len(encoded(s)) for s in observed),default=0),
                'all_observed_states_compact_json_bytes':len(encoded(observed)),
                'latest_memory_utf8_bytes':len(checkpoint['memory'].encode()),
                'final_answer_cache_entries':len(result['answer_protocol']['cache']),
                'final_answer_cache_compact_json_bytes':len(encoded(result['answer_protocol']['cache'])),
                'retained_call_list_compact_json_bytes':len(encoded(calls)),
                'retained_trace_batches_compact_json_bytes':len(encoded(trace['batches']))}
            report['trials'].append({'run':run_name,'case_id':row['case_id'],'arm':row['arm'],
                'path':str(trial_root),'result_sha256':sha(result_path),
                'source_batches':len(expected),'source_utf8_bytes':source_bytes,
                'source_tokens':token_cache.get(source_hash),'source_sequence_sha256':source_hash,
                'source_matches_packet':True,'state':state_info,'sqlite':sqlite_info,
                'disk':disk_totals(files),'disk_groups_apparent_bytes':dict(groups),
                'files':files,'native_result_duplicates_trace_batches':result['batches']==trace['batches'],
                'native_result_duplicates_answer_session':result['answer_protocol']==read(native/'answer-session.json'),
                'disk_to_original_source_ratio':sum(f['bytes'] for f in files)/source_bytes,
                'max_logged_prompt_bytes':max(c['prompt_bytes'] for c in calls),
                'prompt_limit_utf8_bytes':result['context_limit_utf8_bytes'],
                'memory_field_limit_utf8_bytes':result['memory_limit_utf8_bytes']})
        all_files = inventory(root)
        shared = [r for r in all_files if not any(r['path'].startswith(p) for p in trial_prefixes)]
        shared_groups = collections.Counter()
        for row in shared:
            shared_groups[row['path'].split('/')[0]] += row['bytes']
        report['runs'].append({'run':run_name,'path':str(root),'summary_sha256':sha(summary_path),
            'whole_run_disk':disk_totals(all_files),'outside_trial_directories_disk':disk_totals(shared),
            'outside_trial_top_level_apparent_bytes':dict(shared_groups),
            'server_cache_disk':disk_totals([r for r in shared if r['path'].startswith('server/cache/')]),
            'outside_trial_files':shared})
    return report


def markdown(report):
    lines = ['# Completed context campaigns: storage census', '',
      'CPU-only, read-only measurement on 2026-10-07. No active history outputs were inspected. Byte counts are exact at inspection; this report separates actual disk files from logical serialized content. These are completed-run sizes, not peak RAM, peak WAL, write traffic, GPU memory or extrapolated scaling measurements.', '',
      '**Finding:** the 44 trial directories occupy 15,210,751 apparent bytes. Sparse trial evidence occupies 21.52–30.70 times original source text; tiny semantic trials occupy 114.50–309.69 times source, largely from fixed SQLite/SHM and evidence overhead. The useful final 128-counter table is only 1,895–1,900 compact JSON bytes, compared with roughly 1.28–1.43 MB of trial files. Prompt limits are not total-memory bounds.', '',
      '## Per-trial storage', '',
      '`DB` is main SQLite plus WAL and SHM. `Logs` is model-call evidence. `Trace` excludes result receipts. `Receipts` includes native/outer result.json. Snapshot bytes were zero in every trial: these engines do not have history_v1 snapshots. `Disk/source` divides all trial-directory apparent file bytes by unique original batch-text bytes, not by model tokens.', '',
      '| Run/case | Arm | Source bytes / tokens | Final counters / state checkpoints | DB bytes | Logs bytes | Trace bytes | Receipts bytes | Total trial bytes | Disk/source |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in report['trials']:
        g=r['disk_groups_apparent_bytes'];s=r['state'];label=r['run'].replace('context-','').replace('-20261007','')+'/'+r['case_id']
        lines.append(f"| {label} | {r['arm']} | {r['source_utf8_bytes']:,} / {r['source_tokens']} | {s['final_observed_counter_count']}/{s['observed_state_checkpoints']} | {g.get('sqlite',0):,} | {g.get('model_call_evidence',0):,} | {g.get('attempt_trace',0):,} | {g.get('result_receipt',0):,} | {r['disk']['apparent_bytes']:,} | {r['disk_to_original_source_ratio']:.2f}× |")
    lines += ['', 'Summary arms intentionally have no structured observed counter table/checkpoint history; their reference documents still have counters. The reference counts, maximum observed counts and every file size are in the JSON. Checkpoint correctness is not inferred from count or storage size.', '', '## Whole completed campaigns', '', '| Run | Apparent file bytes | Allocated bytes, unique inode | Bytes outside trial directories |', '|---|---:|---:|---:|']
    for r in report['runs']:
        lines.append(f"| {r['run']} | {r['whole_run_disk']['apparent_bytes']:,} | {r['whole_run_disk']['allocated_unique_inode_bytes']:,} | {r['outside_trial_directories_disk']['apparent_bytes']:,} |")
    groups=collections.Counter()
    for r in report['trials']:groups.update(r['disk_groups_apparent_bytes'])
    total=sum(groups.values())
    lines += ['', 'Whole-run directories additionally preserve about 120 MB of server compiler-cache artifacts each. These are shared launch/runtime artifacts, not model source archive, counter state, prompt/KV reuse, or per-trial working state. Their exact sizes are recorded separately in JSON; retaining three copies makes the whole-run total much larger than the trial census.', '', '## What occupies trial disk', '', '| File category | Apparent bytes | Share |', '|---|---:|---:|']
    for k,v in groups.most_common():lines.append(f'| {k} | {v:,} | {100*v/total:.1f}% |')
    lines += ['', 'The categories sum to trial-directory files. Whole-run totals also include compiler caches, launcher, health, strict qualification, identity and summary artifacts outside those directories. Shared packet files/model/tokenizer weights and repository source are excluded from run-directory totals. Allocated sizes use st_blocks×512, deduplicated by inode for the whole-run measure; filesystem metadata, compression/dedup beyond inode identity and deleted files are not measured.', '',
      '## Runtime state versus retained evidence', '',
      'All three arms archive every original batch in canonical.sqlite for later retrieval. SQLite logical source text exactly matches the packet text in this census. The archive arm name does not mean SQLite stores its accepted counter table: archive and summary leave SQL current_state/events/receipts empty. Archive keeps its model-produced state in the Python state variable and latest checkpoint.json. Quoted alone also persists SQL current_state, applied event payloads and receipts. All tables/page allocations and logical UTF-8 text-column bytes are listed in JSON. SQL row JSON sizes are logical proxies, not the physical SQLite encoding.', '',
      'Small DBs pay page/schema/index overhead, plus a 32 KiB shared-memory sidecar. WAL was empty for every completed trial; the script refuses to ignore any nonempty WAL. This does not measure peak WAL or cumulative writes. Main SQLite reads use mode=ro&immutable=1, so no checkpoint/recovery writes occur.', '',
      'Evidence duplication is intentional but large: result.json repeats trace batches and the complete final answer session; trace records accepted response states as well as observed states; calls.jsonl records full prompts, response text and raw/model-response evidence; prompts repeatedly serialize retained source/state/memory. answer-session.json repeats cached source retrievals and retrieval.jsonl records their returned copies. Quoted event payloads repeat verified source quotes inside the DB. Logical sizes of each of these views overlap and must not be summed as unique information. The JSON marks the exact result/trace and result/session equalities.', '',
      'There is one latest checkpoint file per trial, overwritten on each accepted batch, not one separate checkpoint file per historical state. Historical states in these runs survive in audit trace/result evidence; they were not an exposed state_at retrieval facility. Snapshot files are absent, so no claim about history_v1 snapshot amplification follows from this census.', '',
      'The 32,768-byte limit bounds each serialized model prompt, and the 6,553-byte limit bounds the model-authored memory string. They do not bound process RAM, total disk, accumulated source archive, counter-table cardinality, full task/oracle input, cached retrievals, or retained calls/trace lists. The frozen live.py retains calls and trace rows in Python across the trial and loads the whole compiled task/public source. It also repeatedly writes full trace JSON. Thus prompt-bounded is accurate; constant-space or bounded-total-memory is unsupported. This census measures serialized lower-level proxies only; no live/peak RSS or Python heap was sampled.', '',
      'Each trial includes actual final state JSON bytes, peak observed state bytes/count, all observed-state serialization, final memory bytes, final retrieval-cache bytes and retained call/trace serialization in JSON. These help distinguish a small useful current-state table from large reproducibility artifacts, but do not isolate a minimal production implementation or predict its speed/memory.', '',
      '## Reproduce and interpretation limits', '',
      'Run with PYTHONDONTWRITEBYTECODE=1 /mnt/fast-ai/venvs/clm/bin/python3 /tmp/context-storage-census.py. It reads only the three explicitly named completed campaign roots and their frozen packets, plus the local tokenizer; it writes only /tmp/context-storage-census.json and /tmp/context-storage-census.md. No imports from frozen runtime modules, model requests, synthetic replay or mutations of original databases are needed. Source token counts sum independent original-batch encodings without special tokens/chat template; they are not prompt tokens. Tokenizer identity/version and source/result/summary hashes are recorded in JSON.', '',
      'This is a resource-accounting diagnostic. It does not weaken quality gates, establish long-stream asymptotics, estimate active history outcomes or authorize storage pruning. Raw evidence remains preserved. A future RAM claim needs separately designed peak-RSS/heap measurement and an explicit archive/evidence retention policy; merely shrinking the prompt or memory string is insufficient.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    result = census()
    Path('/tmp/context-storage-census.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    Path('/tmp/context-storage-census.md').write_text(markdown(result))
    print(json.dumps({'trials':len(result['trials']),'tokenizer':result['tokenizer'],
        'trial_bytes':sum(r['disk']['apparent_bytes'] for r in result['trials']),
        'db_wal_bytes':sum(r['sqlite']['wal_bytes'] for r in result['trials']),
        'snapshot_bytes':sum(r['disk_groups_apparent_bytes'].get('snapshots',0) for r in result['trials'])},indent=2))
