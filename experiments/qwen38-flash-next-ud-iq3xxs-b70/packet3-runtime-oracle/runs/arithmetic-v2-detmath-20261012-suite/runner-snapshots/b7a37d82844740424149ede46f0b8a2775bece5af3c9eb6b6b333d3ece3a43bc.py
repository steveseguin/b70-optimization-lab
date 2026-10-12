#!/usr/bin/env python3
"""CPU-only suite orchestration; frozen binary, atomic prompt publication, no retry."""
import argparse
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import struct
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
LANE = ROOT / 'experiments/qwen38-flash-next-ud-iq3xxs-b70'
INPUTS = ROOT / 'experiments/own-xpu-runtime/stage2/suite-inputs-20261012'
SEALED = HERE.parent / 'arithmetic-v2-detmath-20261011'
P17 = ROOT / 'experiments/own-xpu-runtime/stage2/packet17-detmath'
PREP = ROOT / 'experiments/own-xpu-runtime/stage2/packet29-merged/prepare.py'
PROMPTS = LANE / 'packet2-cpu-oracle/prompts/prompts.json'
ACCEPTANCE = ROOT / 'experiments/own-xpu-runtime/stage2/packet31-mtp-acceptance/acceptance.json'
PREFIX = ['nice', '-n', '19', 'ionice', '-c', '3']
ENV = {**os.environ, 'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '1',
       'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}

def read(p):
    return json.loads(p.read_text())

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(p, value):
    temp = p.with_name(p.name + '.tmp')
    with temp.open('w') as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())
    temp.replace(p)

def utc():
    return datetime.now(timezone.utc).isoformat()

def rows(p):
    return [json.loads(line) for line in p.read_text().splitlines()]

def check(condition, message):
    if not condition:
        raise RuntimeError(message)

def preflight():
    check(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    check(os.environ.get('OMP_NUM_THREADS') == '2', 'OMP_NUM_THREADS=2 required')
    check('idle' in subprocess.check_output(PREFIX + ['ionice', '-p', str(os.getpid())], text=True), 'idle IO required')
    affinity = sorted(os.sched_getaffinity(0))
    check(not set(affinity).intersection({0, 1, 2, 3, 16, 17, 18, 19}), 'reserved CPU affinity')
    sealed = read(SEALED / 'receipt.json')
    binary = ROOT / sealed['command'][0]
    check(binary.is_file() and sha(binary) == sealed['binary_sha256'], 'sealed CPU binary unavailable or changed; stop for rebuild proof')
    for name, digest in sealed['arithmetic']['arithmetic_sources'].items():
        check(sha(ROOT / name) == digest, 'arithmetic source changed: ' + name)
    deps = subprocess.check_output(PREFIX + ['readelf', '-d', str(binary)], text=True)
    for forbidden in ('libsycl', 'libze_loader', 'libOpenCL', 'libcuda'):
        check(forbidden not in deps, 'device dependency: ' + forbidden)
    # Refuse a new campaign if any previous CPU oracle survived its supervisor.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc/'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        check(not (argv and argv[0].decode(errors='replace') == str(binary)),
              'existing CPU oracle PID ' + proc.name + '; no duplicate launch')
    prompt_manifest = read(PROMPTS)
    check(sha(ROOT / prompt_manifest['suite_path']) == prompt_manifest['suite_sha256'], 'suite changed')
    for row in prompt_manifest['prompts']:
        check(sha(Path(row['file'])) == row['rendered_sha256'], 'rendered prompt changed')
    check(shutil.disk_usage(HERE).free > 2_000_000_000, 'less than 2 GB output working reserve')
    return sealed, binary, affinity, prompt_manifest

def prepare(row):
    dest = INPUTS / row['id']
    if not dest.exists():
        temp = INPUTS / ('.' + row['id'] + '.partial-' + str(time.time_ns()))
        # The existing CPU prepare implementation is imported without running device code.
        spec = importlib.util.spec_from_file_location('suite_prepare', PREP)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.prepare(temp, Path(row['file']))
        inp = read(temp / 'input.json')
        check(inp['prompt_sha256'] == row['rendered_sha256'], 'prompt binding')
        check(list(map(int, (temp / 'tokens.txt').read_text().split())) == inp['tokens'], 'bundle token equality')
        check(len(inp['tokens']) + 63 <= 192, 'prompt exceeds frozen context')
        for name, digest in inp['files'].items():
            check(sha(temp / name) == digest, 'bundle file hash')
        temp.rename(dest)
    inp = read(dest / 'input.json')
    check(inp['prompt_sha256'] == row['rendered_sha256'], 'existing bundle prompt binding')
    check(list(map(int, (dest / 'tokens.txt').read_text().split())) == inp['tokens'], 'existing bundle token equality')
    for name, digest in inp['files'].items():
        check(sha(dest / name) == digest, 'existing bundle changed')
    return dest, inp

def validate(directory, bundle):
    result = read(directory / 'result.json')
    check(result['status'] in ('eos', 'token-cap') and not result['error'], 'incomplete native result')
    check(result['arithmetic'] == 'iq3-p17-detmath-v2' and result['device_executed'] is False, 'oracle identity')
    tokens = result['tokens']
    check(1 <= len(tokens) <= 64, 'token count')
    check(not any(t in (248044, 248046) for t in tokens[:-1]), 'tokens after EOG')
    check((result['status'] == 'eos') == (tokens[-1] in (248044, 248046)), 'EOG status')
    check(result['status'] == 'eos' or len(tokens) == 64, 'short non-EOG result')
    inp = read(bundle / 'input.json')
    check((directory / 'input.json').read_bytes() == (bundle / 'input.json').read_bytes(), 'oracle copied input differs')
    tokenrows = rows(directory / 'tokens.jsonl')
    check(tokenrows == result['steps'] and [r['token_id'] for r in tokenrows] == tokens, 'token log mismatch')
    check([r['step'] for r in tokenrows] == list(range(1, len(tokens)+1)), 'token indices')
    positions = rows(directory / 'positions.jsonl')
    consumed = inp['tokens'] + tokens[:-1]
    check([r['position'] for r in positions] == list(range(len(consumed))), 'position coverage')
    check([r['input_token'] for r in positions] == consumed, 'consumed token proof')
    hashes = {}
    check({p.name for p in directory.glob('step*')} == {f'step{i}' for i in range(1, min(8, len(tokens))+1)}, 'fixture step coverage')
    for i in range(1, min(8, len(tokens))+1):
        d = directory / f'step{i}'
        records = rows(d / 'layers.jsonl')
        check([r['layer'] for r in records] == list(range(48)), 'layer coverage')
        for r in records:
            p = d / f"layer-{r['layer']:02}.bf16"
            check(p.stat().st_size == 20480 and r['shape'] == [1,4,2560] and r['dtype'] == 'BF16 little-endian' and sha(p) == r['sha256'], 'fixture hash/shape')
            hashes[str(p.relative_to(directory))] = sha(p)
    teardown = read(directory / 'teardown.json')
    check(len(teardown) == 1 and teardown[0]['safe_to_exit'] and teardown[0]['live_bytes'] == teardown[0]['in_flight'] == 0, 'unsafe CPU teardown')
    return dict(passed=True, fixture_hashes=hashes, generated_tokens=len(tokens),
                prompt_tokens=len(inp['tokens']), consumed_tokens_exact=True,
                positions=len(positions), mean_seconds_per_position=sum(r['seconds'] for r in positions)/len(positions))

def equality(directory):
    other = SEALED / 'incident-retrospective'
    a, b = read(directory / 'result.json'), read(other / 'result.json')
    check(a['tokens'] == b['tokens'], 'sealed tokens disagree')
    check(a['text'] == b['text'], 'sealed decoded text disagrees')
    payload_keys = ('step', 'token_id', 'top5_ids', 'top5_logits', 'logits_bf16_sha256')
    for x, y in zip(a['steps'], b['steps']):
        check(all(x[k] == y[k] for k in payload_keys), 'sealed token/logit record differs')
    names = sorted(str(p.relative_to(other)) for p in other.glob('step*/*'))
    proof = {}
    for name in names:
        check((directory / name).read_bytes() == (other / name).read_bytes(), 'sealed fixture differs: ' + name)
        proof[name] = sha(directory / name)
    check(len(names) == 392, 'sealed fixture file coverage')
    # Tokens have no standalone file in the sealed run; compare canonical int32 bytes.
    tokenbytes = struct.pack('<64i', *a['tokens'])
    check(tokenbytes == struct.pack('<64i', *b['tokens']), 'token bytes')
    return dict(passed=True, tokens=64, raw_fixtures=384, layer_hash_ledgers=8,
                token_int32le_sha256=hashlib.sha256(tokenbytes).hexdigest(), fixture_hashes=proof,
                all_64_logits_and_top5_equal=True, text_equal=True,
                sealed_receipt_sha256=sha(SEALED/'receipt.json'),
                note='Timing, PID, paths and receipts differ; all numerical evidence is exact.')

def packet31(directory, prompt):
    if prompt not in ('code-review', 'customer-email', 'benchmark-analysis'):
        return None
    selected = sorted((r for r in read(ACCEPTANCE)['positions'] if r['prompt'] == prompt), key=lambda r:r['generated_index'])
    check([r['generated_index'] for r in selected] == list(range(64)), 'packet31 coverage')
    expected = [r['target_token'] for r in selected]
    actual = read(directory / 'result.json')['tokens']
    return dict(passed=actual == expected, acceptance_sha256=sha(ACCEPTANCE),
                expected_tokens=expected, oracle_tokens=actual,
                first_difference=next((i+1 for i in range(max(len(actual),len(expected))) if i>=len(actual) or i>=len(expected) or actual[i]!=expected[i]), None))

def compress(directory, receipt):
    receipt['compressed_logs'] = {}
    for name in ('progress.jsonl', 'timings.jsonl'):
        source = directory / name
        if not source.exists():
            with gzip.open(directory/(name+'.gz'), 'rb') as restored:
                digest = hashlib.sha256(); size = 0
                while block := restored.read(1024*1024):
                    digest.update(block); size += len(block)
            receipt['compressed_logs'][name] = dict(sha256=digest.hexdigest(), bytes=size)
            continue
        digest = sha(source)
        receipt['compressed_logs'][name] = dict(sha256=digest, bytes=source.stat().st_size)
        temp = directory / (name + '.gz.tmp')
        with source.open('rb') as src, temp.open('wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as dst:
                shutil.copyfileobj(src, dst)
        with gzip.open(temp, 'rb') as f:
            check(hashlib.file_digest(f, 'sha256').hexdigest() == digest, 'compressed log restoration')
        temp.rename(directory / (name + '.gz'))
        source.unlink()

def run_prompt(row, sealed, binary, affinity):
    check(sha(binary) == sealed['binary_sha256'], 'sealed binary changed between prompts')
    for name, digest in sealed['arithmetic']['arithmetic_sources'].items():
        check(sha(ROOT/name) == digest, 'arithmetic source changed between prompts: ' + name)
    prompt = row['id']
    dest = HERE / prompt
    bundle, inp = prepare(row)
    if dest.exists():
        validate(dest, bundle)
        old = read(dest/'receipt.json')
        check(old['verified'] and old['binary_sha256'] == sealed['binary_sha256'], 'unverified existing result')
        check(old['result_sha256'] == sha(dest/'result.json') and old['input_sha256'] == sha(bundle/'input.json'), 'existing receipt hashes changed')
        check(old['validation_sha256'] == sha(dest/'validation.json'), 'existing fixture validation changed')
        check(read(dest/'arithmetic.json') == sealed['arithmetic'], 'existing arithmetic differs')
        if prompt == 'incident-retrospective':
            check(read(dest/'equality-proof.json') == equality(dest), 'existing equality proof changed')
        matched = packet31(dest, prompt)
        check(matched is None or matched['passed'], 'existing packet31 token disagreement')
        refresh()
        return
    if prompt != 'incident-retrospective':
        check(read(HERE/'incident-retrospective'/'equality-proof.json')['passed'], 'incident equality gate required')
    for previous in sorted(HERE.glob('.' + prompt + '.partial-*'), reverse=True):
        native = previous/'native'
        if not (native/'result.json').exists() or not (native/'teardown.json').exists():
            continue
        if read(native/'result.json').get('status') not in ('token-cap','eos'):
            continue
        prior = read(previous/'receipt.json')
        check(prior['binary_sha256'] == sealed['binary_sha256'] and prior['input_sha256'] == sha(bundle/'input.json'), 'completed partial identity mismatch')
        if 'cpu_seconds' not in prior:
            # Native output survived, but wait4 CPU accounting did not. Do not invent it.
            prior.update(cpu_seconds=None, cpu_accounting_lost_on_resume=True,
                         elapsed_seconds=read(native/'result.json')['seconds'],
                         completed_utc=utc(), returncode=None)
        finalize_prompt(row, sealed, bundle, inp, previous, native, dest, prior)
        return
    attempt = HERE / ('.' + prompt + '.partial-' + str(time.time_ns()))
    attempt.mkdir()
    directory = attempt / 'native'
    cmd = PREFIX + [str(binary), str(bundle), str(directory), '10800', '64']
    receipt = dict(schema='iq3-runtime-cpu-oracle.run.v1', status='running', verified=False,
                   started_utc=utc(), command=cmd, arithmetic=sealed['arithmetic'],
                   binary_sha256=sha(binary), source_hashes=sealed['arithmetic']['arithmetic_sources'],
                   runner_sha256=sha(Path(__file__)), prepare_sha256=sha(PREP),
                   model=sealed['model'], prompt_id=prompt, prompt_sha256=row['rendered_sha256'],
                   prompt_tokens=len(inp['tokens']), requested_tokens=64, context=192,
                   input_sha256=sha(bundle/'input.json'), device_executed=False, nice=19,
                   ionice='idle', OMP_NUM_THREADS=2, affinity=affinity,
                   address_space_cap_bytes=38_000_000_000, anonymous_memory_guard_bytes=10_000_000_000)
    snapshot = HERE/'runner-snapshots'/(receipt['runner_sha256']+'.py')
    snapshot.parent.mkdir(exist_ok=True)
    if not snapshot.exists():
        shutil.copyfile(Path(__file__), snapshot)
    save(attempt/'receipt.json', receipt)
    start = time.monotonic()
    cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    maximum_anon = 0
    last_positions = -1
    with (attempt/'stdout.txt').open('w') as log:
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env={**ENV, 'IQ3_MODEL_DIR':inp['model_dir']})
        receipt['pid'] = child.pid
        save(attempt/'receipt.json', receipt)
        def stop(sig, frame):
            if child.poll() is None:
                child.send_signal(sig)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        while child.poll() is None:
            anon = 0
            for pid in (os.getpid(), child.pid):
                try:
                    data = Path(f'/proc/{pid}/status').read_text().splitlines()
                    anon += next(int(s.split()[1])*1024 for s in data if s.startswith('RssAnon:'))
                except (FileNotFoundError, StopIteration):
                    pass
            maximum_anon = max(maximum_anon, anon)
            if anon >= 10_000_000_000 or time.monotonic()-start > 10860:
                child.send_signal(signal.SIGTERM)
                child.wait(timeout=60)
                raise RuntimeError('CPU memory/time guard: stopped; no retry')
            posfile = directory/'positions.jsonl'
            if posfile.exists():
                lines = posfile.read_text().splitlines()
                try:
                    last = json.loads(lines[-1]) if lines else None
                except json.JSONDecodeError:
                    last = None
                if last and last['position'] != last_positions:
                    last_positions = last['position']
                    status = dict(status='running', prompt=prompt, completed_positions=last_positions+1,
                                  prompt_positions=len(inp['tokens']), last_position=last,
                                  elapsed_seconds=time.monotonic()-start, anonymous_bytes=anon,
                                  peak_anonymous_bytes=maximum_anon, pid=child.pid, updated_utc=utc())
                    save(HERE/'status.json', status)
            time.sleep(1)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt.update(returncode=child.returncode, elapsed_seconds=time.monotonic()-start,
                   cpu_seconds=after.ru_utime+after.ru_stime-cpu_before.ru_utime-cpu_before.ru_stime,
                   peak_anonymous_bytes=maximum_anon, completed_utc=utc())
    save(attempt/'receipt.json', receipt)
    check(child.returncode == 0, 'native CPU process failed; retained partial attempt')
    finalize_prompt(row, sealed, bundle, inp, attempt, directory, dest, receipt)

def finalize_prompt(row, sealed, bundle, inp, attempt, directory, dest, receipt):
    prompt = row['id']
    result = read(directory/'result.json')
    vocab = []
    with (bundle/'vocab.bin').open('rb') as f:
        while h := f.read(4):
            vocab.append(f.read(struct.unpack('<I', h)[0]))
    result.update(text=b''.join(vocab[t] for t in result['tokens']).decode('utf-8', errors='replace'),
                  prompt_tokens=len(inp['tokens']), id=prompt)
    save(directory/'result.json', result)
    save(directory/'arithmetic.json', sealed['arithmetic'])
    validation = validate(directory, bundle)
    save(directory/'validation.json', validation)
    if prompt == 'incident-retrospective':
        save(directory/'equality-proof.json', equality(directory))
    p31 = packet31(directory, prompt)
    if p31 is not None:
        save(directory/'packet31-comparison.json', p31)
        if not p31['passed']:
            save(HERE/'STOP-disagreement.json', dict(prompt=prompt, attempt=str(attempt), **p31))
            raise RuntimeError('packet31 CPU tokens disagree; stop entire suite')
    compress(directory, receipt)
    receipt.update(status=result['status'], verified=True, result_sha256=sha(directory/'result.json'),
                   validation_sha256=sha(directory/'validation.json'),
                   coverage={k:validation[k] for k in ('prompt_tokens','generated_tokens')},
                   mean_seconds_per_position=validation['mean_seconds_per_position'],
                   seconds_per_position_sha256=sha(directory/'positions.jsonl'))
    save(directory/'receipt.json', receipt)
    shutil.copyfile(attempt/'stdout.txt', directory/'stdout.txt')
    directory.rename(dest)
    # The small outer attempt receipt remains ignored as a crash/recovery breadcrumb.
    refresh()
    save(HERE/'status.json', dict(status='prompt-verified', prompt=prompt, updated_utc=utc()))
    print(prompt + ': verified', flush=True)

def refresh():
    entries = []
    for row in read(PROMPTS)['prompts']:
        prompt = row['id']
        d, bundle = HERE/prompt, INPUTS/prompt
        if not (d/'receipt.json').exists():
            continue
        r, result = read(d/'receipt.json'), read(d/'result.json')
        if not r.get('verified'):
            continue
        entries.append(dict(prompt_id=prompt, prompt_tokens=r['prompt_tokens'],
                            input_bundle=str(bundle.relative_to(ROOT)),
                            input_bundle_hashes={f.name:sha(f) for f in sorted(bundle.iterdir()) if f.is_file()},
                            oracle_directory=str(d.relative_to(ROOT)), oracle_receipt_sha256=sha(d/'receipt.json'),
                            generated_tokens=len(result['tokens']), first_8_token_ids=result['tokens'][:8],
                            ended_early=len(result['tokens'])<64, termination=result['status'],
                            mean_seconds_per_position=r['mean_seconds_per_position'],
                            elapsed_seconds=r['elapsed_seconds'], cpu_seconds=r['cpu_seconds']))
    manifest = dict(schema='own-runtime.iq3.suite-inputs.v1', arithmetic='iq3-p17-detmath-v2', context=192,
                    token_cap=64, suite_sha256=read(PROMPTS)['suite_sha256'], prompts_manifest_sha256=sha(PROMPTS),
                    complete=len(entries)==12, prompts=entries,
                    total_elapsed_seconds=sum(e['elapsed_seconds'] for e in entries),
                    total_cpu_hours=sum(e['cpu_seconds'] or 0 for e in entries)/3600,
                    cpu_accounting_complete=all(e['cpu_seconds'] is not None for e in entries))
    save(INPUTS/'suite-manifest.json', manifest)
    table = '| Prompt | Prompt tokens | Generated | First 8 token IDs | Early end | Seconds/position |\n| --- | ---: | ---: | --- | --- | ---: |\n'
    for e in entries:
        table += f"| {e['prompt_id']} | {e['prompt_tokens']} | {e['generated_tokens']} | {', '.join(map(str,e['first_8_token_ids']))} | {e['ended_early']} | {e['mean_seconds_per_position']:.4f} |\n"
    text = f'''# Arithmetic-v2 twelve-prompt CPU suite

Verified prompts: {len(entries)}/12. Complete: {manifest['complete']}.
The unchanged sealed CPU binary generates greedy tokens for the fixed rendered suite.
Identity: `iq3-p17-detmath-v2`; 192-token context; maximum 64 generated tokens.
EOS (248044) or 248046 is saved and then stops generation. No padding or forced continuation.
The runtime uses the same stop rule. llama.cpp's immediate code-review EOG is information only.
Two OpenMP threads, nice 19, idle I/O; inherited CPU affinity, no device execution.

{table}
Total numerical-process wall time: {manifest['total_elapsed_seconds']:.3f} seconds.
Actual process CPU time (user + system): {manifest['total_cpu_hours']:.6f} CPU hours.
CPU accounting complete: {manifest['cpu_accounting_complete']}.
Position timings include bounded weight reads and CPU work; these are oracle costs, not serving speeds.
Every prompt retains `positions.jsonl`; means above include prefill and decode positions.

Incident equality: {'64/64 token IDs, 64 logit hashes/top-five records, 384/384 raw BF16 fixtures and 8/8 layer hash ledgers exactly equal; see incident-retrospective/equality-proof.json in the oracle directory.' if entries else 'pending; all other oracle runs are gated on this proof.'}
Timing and process metadata naturally differ. Input bundles are made by packet29 `prepare.py`;
`validation.json` proves `tokens.txt`, `input.json`, the oracle copy and consumed positions agree.

Retain raw 20,480-byte layer files for steps 1–8 (or through early EOS), tokens/text,
receipts and all timing evidence. Progress/timing site logs use deterministic gzip (mtime=0),
verified against original SHA256 before deleting raw copies. Keep teardown JSON uncompressed,
as in the sealed run. Files above 1 MiB are these same retained logs/teardown and each bundle's
2.84 MB `vocab.bin`, required by the runtime to decode tokens. No models or executables are committed.
Each compressed log's original hash/size is in its receipt. Restore with gzip and verify that hash.

Run from the repository root (Python environment needs the existing `regex` dependency):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/vllm-xpu/bin/python -B {HERE.relative_to(ROOT)}/suite_run.py --all --publish
nice -n 19 ionice -c 3 python3 -B {HERE.relative_to(ROOT)}/suite_check.py RUNTIME_OUTPUTS
```

The checker accepts `RUNTIME_OUTPUTS/<prompt>/` or `<prompt>/run/`, reads runtime
`receipt.json` tokens, and compares raw step fixtures without tolerance. Using the oracle
suite directory itself tests the retained oracle files. It prints all twelve rows and fails
if any prompt is missing or incomplete. Unit tests include altered tokens, missing bytes,
corruption with a rewritten ledger, manifest tampering, early EOS and runtime nesting.
`checker-tests.json` pins the test/checker source and records the test result.

For packet29 `window.py`, pass `--input` the bundle directory and `--oracle` the matching
oracle directory from `suite-manifest.json`. The native program's `--input` takes that
bundle's `tokens.txt` instead. The frozen window gate assumes the requested token count;
an early-EOS oracle must not be padded to satisfy that assumption.

`status.json` is updated after each completed position. Each prompt runs in a private
`.partial-*` directory; after validation it is renamed to its final prompt ID. A restart
verifies completed prompt hashes and skips their computation; completed native partials
are recovered without rerunning. An interrupted unfinished prompt starts a new attempt,
retaining old partial evidence. A surviving oracle blocks duplicate launches. No automatic
retry occurs after native failure or packet31 disagreement. Completed prompts are committed
with explicit paths and pushed only when main is a fast-forward; no stash or branches.
The incident repeat's original launcher is retained under `runner-snapshots/` by hash;
subsequent launcher revisions preserve the same numerical binary and arithmetic.

This is oracle coverage, not a runtime speed result or the 512-token final performance gate.
Only incident-retrospective is a new full fresh-process repeat; other prompts have one new oracle run.
The reference screen uses two repeats; runtime qualification still requires its own repeats.
'''
    for root in (HERE, INPUTS):
        temporary = root/'README.md.tmp'
        temporary.write_text(text)
        check(temporary.read_text() == text, 'README write verification')
        temporary.replace(root/'README.md')

def publish(prompt):
    def git(*args):
        return subprocess.check_output(PREFIX+['git', '-c', 'pack.threads=1', '-c', 'index.threads=1', *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT)
    check(git('branch','--show-current').strip() == 'main', 'main only')
    check(not git('diff','--cached','--name-only').strip(), 'unrelated staged files; do not commit')
    paths = [HERE/prompt, INPUTS/prompt, HERE/'suite_run.py', HERE/'runner-snapshots', HERE/'.gitignore', HERE/'README.md', INPUTS/'.gitignore', INPUTS/'README.md', INPUTS/'suite-manifest.json']
    for name in ('suite_check.py', 'test_suite_check.py', 'checker-tests.json'):
        if (HERE/name).exists(): paths.append(HERE/name)
    paths = [str(p.relative_to(ROOT)) for p in paths]
    git('add','--',*paths)
    git('diff','--cached','--check')
    if git('diff','--cached','--name-only').strip():
        print(git('commit','--quiet','-m',f'Add verified arithmetic-v2 suite oracle: {prompt}','-m','Co-Authored-By: Codex <noreply@openai.com>'), flush=True)
    git('fetch','origin','main')
    check(subprocess.call(PREFIX+['git','merge-base','--is-ancestor','origin/main','HEAD'],cwd=ROOT)==0, 'remote main diverged; no rebase or stash; focused commit retained')
    print(git('push','origin','HEAD:main'), flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--publish', action='store_true')
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()
    with (HERE/'.runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        sealed, binary, affinity, prompts = preflight()
        if args.refresh:
            refresh()
            return
        check(args.prompt or args.all, 'select prompt or --all')
        selected = [r for r in prompts['prompts'] if args.all or r['id']==args.prompt]
        check(bool(selected), 'unknown prompt')
        for row in selected:
            check(not (HERE/'STOP-disagreement.json').exists(), 'CPU disagreement latch present')
            run_prompt(row, sealed, binary, affinity)
            if args.publish:
                publish(row['id'])
        save(HERE/'status.json', dict(status='selected-prompts-complete', updated_utc=utc()))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        save(HERE/'status.json', dict(status='stopped', error=str(error), updated_utc=utc()))
        raise
