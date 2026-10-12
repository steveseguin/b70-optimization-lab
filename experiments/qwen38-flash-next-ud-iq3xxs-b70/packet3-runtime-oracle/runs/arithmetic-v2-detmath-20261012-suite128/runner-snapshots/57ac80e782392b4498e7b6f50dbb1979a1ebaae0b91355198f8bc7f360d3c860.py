#!/usr/bin/env python3
"""CPU-only suite orchestration; frozen binary, atomic prompt publication, no retry."""
import argparse
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
import multiprocessing
import queue
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
INPUTS = ROOT / 'experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128'
SEALED = HERE.parent / 'arithmetic-v2-detmath-20261011'
P17 = ROOT / 'experiments/own-xpu-runtime/stage2/packet17-detmath'
PREP = ROOT / 'experiments/own-xpu-runtime/stage2/packet29-merged/prepare.py'
PROMPTS = LANE / 'packet2-cpu-oracle/prompts/prompts.json'
ACCEPTANCE = ROOT / 'experiments/own-xpu-runtime/stage2/packet31-mtp-acceptance/acceptance.json'
OLD = HERE.parent / 'arithmetic-v2-detmath-20261012-suite'
OLD_INPUTS = ROOT / 'experiments/own-xpu-runtime/stage2/suite-inputs-20261012'
PREFIX = ['nice', '-n', '19', 'ionice', '-c', '3']
ENV = {**os.environ, 'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '1',
       'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}

def read(p):
    return json.loads(p.read_text())

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(p, value):
    temp = p.with_name(p.name + '.' + str(os.getpid()) + '.tmp')
    with temp.open('w') as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())
    check(json.loads(temp.read_text())==value,'atomic JSON readback')
    temp.replace(p)

def utc():
    return datetime.now(timezone.utc).isoformat()

def rows(p):
    return [json.loads(line) for line in p.read_text().splitlines()]

def check(condition, message):
    if not condition:
        raise RuntimeError(message)

def disk_guard():
    report = subprocess.check_output(PREFIX + ['df', '-B1', '/'], text=True)
    check(int(report.splitlines()[-1].split()[3]) >= 8_000_000_000,
          'STOP: less than 8 GB free on root filesystem; no further large writes')
    scratch=sum(f.stat().st_size for d in HERE.glob('.*.partial-*') for f in d.rglob('*') if f.is_file())
    check(scratch<2_000_000_000, 'STOP: scratch exceeds 2 GB')
    for root in (HERE, INPUTS):
        build = root/'build'
        check(not build.exists() or sum(f.stat().st_size for f in build.rglob('*') if f.is_file()) < 2_000_000_000,
              'STOP: task build tree is at least 2 GB')

def preflight():
    check(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    check(os.environ.get('OMP_NUM_THREADS') == '2', 'OMP_NUM_THREADS=2 required')
    check('idle' in subprocess.check_output(PREFIX + ['ionice', '-p', str(os.getpid())], text=True), 'idle IO required')
    affinity = sorted(os.sched_getaffinity(0))
    check(not set(affinity).intersection({0, 1, 2, 3, 16, 17, 18, 19}), 'reserved CPU affinity')
    sealed = read(SEALED / 'receipt.json')
    baseline = dict(sealed)
    build = read(HERE/'build-receipt.json')
    check(build['passed'] and build['source_sha256']==sha(HERE/'oracle128.cpp'), 'build binding')
    sealed['binary_sha256'] = build['binary_sha256']
    binary = HERE/'build/oracle'
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
    disk_guard()
    return sealed, binary, affinity, prompt_manifest

def prepare(row):
    # prepare.py takes only a prompt: no cap or context enters these five files.
    bundle = OLD_INPUTS / row['id']
    inp = read(bundle/'input.json')
    check(inp['prompt_sha256']==row['rendered_sha256'], 'bundle prompt binding')
    check(list(map(int,(bundle/'tokens.txt').read_text().split()))==inp['tokens'], 'bundle token binding')
    check(len(inp['tokens'])+127<=256, 'context capacity')
    for name,digest in inp['files'].items():
        check(sha(bundle/name)==digest, 'existing input hash: '+name)
    dest=INPUTS/row['id']; dest.mkdir(exist_ok=True)
    save(dest/'bundle-reference.json', dict(input_bundle=str(bundle.relative_to(ROOT)),
         files={f.name:sha(f) for f in sorted(bundle.iterdir()) if f.is_file()},
         cap_independent=True, prepare_sha256=sha(PREP)))
    return bundle,inp

def fixture_steps(count):
    return [i for i in range(1,count+1) if i<=8 or 97<=i<=104]

def validate(directory, bundle):
    result = read(directory / 'result.json')
    check(result['status'] in ('eos', 'token-cap') and not result['error'], 'incomplete native result')
    check(result['arithmetic'] == 'iq3-p17-detmath-v2' and result['device_executed'] is False, 'oracle identity')
    tokens = result['tokens']
    check(1 <= len(tokens) <= 128, 'token count')
    check(not any(t in (248044, 248046) for t in tokens[:-1]), 'tokens after EOG')
    check((result['status'] == 'eos') == (tokens[-1] in (248044, 248046)), 'EOG status')
    check(result['status'] == 'eos' or len(tokens) == 128, 'short non-EOG result')
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
    check({p.name for p in directory.glob('step*')} == {f'step{i}' for i in fixture_steps(len(tokens))}, 'fixture step coverage')
    for i in fixture_steps(len(tokens)):
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

def compare_prefix(directory, other):
    a,b=read(directory/'result.json'),read(other/'result.json')
    n=len(b['tokens']); check(n<=64, 'reference prefix cap')
    check(a['tokens'][:n]==b['tokens'], 'STOP: prefix tokens disagree: '+str(other))
    keys=('step','token_id','top5_ids','top5_logits','logits_bf16_sha256')
    check(all(all(x[k]==y[k] for k in keys) for x,y in zip(a['steps'][:n],b['steps'])), 'STOP: prefix logits differ')
    names=sorted(str(p.relative_to(other)) for p in other.glob('step*/*'))
    for name in names:
        check((directory/name).read_bytes()==(other/name).read_bytes(), 'STOP: prefix fixture differs: '+name)
    check(len(names)==min(n,8)*49, 'reference fixture coverage')
    return dict(passed=True,reference=str(other.relative_to(ROOT)),reference_result_sha256=sha(other/'result.json'),
        tokens=n,token_int32le_sha256=hashlib.sha256(struct.pack('<'+str(n)+'i',*b['tokens'])).hexdigest(),
        raw_fixtures=min(n,8)*48,layer_hash_ledgers=min(n,8),all_prefix_logits_and_top5_equal=True,
        fixture_hashes={name:sha(directory/name) for name in names})

def equality(directory):
    return compare_prefix(directory, SEALED/'incident-retrospective')

def suite64_equality(directory,prompt):
    other=OLD/prompt
    if not (other/'receipt.json').exists():
        return dict(passed=None,available_at_completion=False,checked_utc=utc())
    check(read(other/'receipt.json')['verified'], 'unverified 64-token reference')
    return dict(**compare_prefix(directory,other),available_at_completion=True,
                reference_receipt_sha256=sha(other/'receipt.json'))

def packet31(directory, prompt):
    if prompt not in ('code-review', 'customer-email', 'benchmark-analysis'):
        return None
    selected = sorted((r for r in read(ACCEPTANCE)['positions'] if r['prompt'] == prompt), key=lambda r:r['generated_index'])
    check([r['generated_index'] for r in selected] == list(range(64)), 'packet31 coverage')
    expected = [r['target_token'] for r in selected]
    actual = read(directory / 'result.json')['tokens'][:64]
    return dict(passed=actual == expected, acceptance_sha256=sha(ACCEPTANCE),
                expected_tokens=expected, oracle_tokens=actual,
                first_difference=next((i+1 for i in range(max(len(actual),len(expected))) if i>=len(actual) or i>=len(expected) or actual[i]!=expected[i]), None))

def compress(directory, receipt):
    disk_guard()
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

def run_prompt(row, sealed, binary, affinity, defer_finalize=False):
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
        check(read(dest/'suite64-equality-proof.json').get('passed') is not False,'old prefix failure')
        suite64_equality(dest,prompt)
        for name,info in old['compressed_logs'].items():
            with gzip.open(dest/(name+'.gz'),'rb') as restored:
                check(hashlib.file_digest(restored,'sha256').hexdigest()==info['sha256'],'restored log hash')
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
        if defer_finalize:
            return (row, sealed, bundle, inp, previous, native, dest, prior)
        finalize_prompt(row, sealed, bundle, inp, previous, native, dest, prior)
        return
    disk_guard()
    check(len(oracle_processes())<3, 'three oracle processes already running')
    attempt = HERE / ('.' + prompt + '.partial-' + str(time.time_ns()))
    attempt.mkdir()
    directory = attempt / 'native'
    cmd = PREFIX + [str(binary), str(bundle), str(directory), '10800', '128']
    receipt = dict(schema='iq3-runtime-cpu-oracle.run.v1', status='running', verified=False,
                   started_utc=utc(), command=cmd, arithmetic=sealed['arithmetic'],
                   binary_sha256=sha(binary), source_hashes=sealed['arithmetic']['arithmetic_sources'],
                   runner_sha256=sha(Path(__file__)), prepare_sha256=sha(PREP),
                   model=sealed['model'], prompt_id=prompt, prompt_sha256=row['rendered_sha256'],
                   prompt_tokens=len(inp['tokens']), requested_tokens=128, context=256,
                   input_sha256=sha(bundle/'input.json'), device_executed=False, nice=19,
                   ionice='idle', OMP_NUM_THREADS=2, affinity=affinity,
                   address_space_cap_bytes=38_000_000_000, anonymous_memory_guard_bytes=3_000_000_000)
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
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env={**ENV, 'IQ3_MODEL_DIR':inp['model_dir'], **({'IQ3_PREFIX_GATE':str(attempt/'prefix-approved')} if prompt=='incident-retrospective' else {})})
        receipt['pid'] = child.pid
        save(attempt/'receipt.json', receipt)
        def stop(sig, frame):
            if child.poll() is None:
                child.send_signal(sig)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        last_disk_check = 0
        while child.poll() is None:
            if time.monotonic() - last_disk_check > 10:
                try:
                    disk_guard()
                except Exception:
                    child.send_signal(signal.SIGTERM)
                    child.wait(timeout=60)
                    raise
                last_disk_check = time.monotonic()
            if prompt=='incident-retrospective' and not (attempt/'prefix-approved').exists() and (directory/'result.json').exists():
                current=read(directory/'result.json')
                if len(current['tokens'])==64:
                    try:
                        proof=equality(directory)
                        save(attempt/'capacity-prefix-proof.json',proof)
                        save(attempt/'prefix-approved',dict(passed=True,checked_utc=utc()))
                        print('Capacity gate PASS: 64 tokens, 384 fixtures, 8 ledgers at context 256',flush=True)
                    except Exception:
                        child.send_signal(signal.SIGTERM); child.wait(timeout=60)
                        raise
            anon = 0
            for pid in (os.getpid(), child.pid):
                try:
                    data = Path(f'/proc/{pid}/status').read_text().splitlines()
                    anon += next(int(s.split()[1])*1024 for s in data if s.startswith('RssAnon:'))
                except (FileNotFoundError, StopIteration):
                    pass
            maximum_anon = max(maximum_anon, anon)
            if anon >= 3_000_000_000 or time.monotonic()-start > 10860:
                child.send_signal(signal.SIGTERM)
                child.wait(timeout=60)
                raise RuntimeError('CPU memory/time guard: stopped; no retry')
            total_anon = sum(p['anon'] for p in oracle_processes()) + anon
            if total_anon>=11_000_000_000:
                child.send_signal(signal.SIGTERM); child.wait(timeout=60)
                raise RuntimeError('STOP: combined oracle anonymous memory guard')
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
                    save(attempt/'status.json', status)
                    save(HERE/'status.json', status)
            time.sleep(1)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt.update(returncode=child.returncode, elapsed_seconds=time.monotonic()-start,
                   cpu_seconds=after.ru_utime+after.ru_stime-cpu_before.ru_utime-cpu_before.ru_stime,
                   peak_anonymous_bytes=maximum_anon, completed_utc=utc())
    save(attempt/'receipt.json', receipt)
    check(child.returncode == 0, 'native CPU process failed; retained partial attempt')
    if defer_finalize:
        return (row, sealed, bundle, inp, attempt, directory, dest, receipt)
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
    save(directory/'suite64-equality-proof.json',suite64_equality(directory,prompt))
    compress(directory, receipt)
    receipt.update(status=result['status'], verified=True, result_sha256=sha(directory/'result.json'),
                   validation_sha256=sha(directory/'validation.json'),
                   coverage={k:validation[k] for k in ('prompt_tokens','generated_tokens')},
                   mean_seconds_per_position=validation['mean_seconds_per_position'],
                   seconds_per_position_sha256=sha(directory/'positions.jsonl'),
                   suite64_equality_sha256=sha(directory/'suite64-equality-proof.json'),
                   build_receipt_sha256=sha(HERE/'build-receipt.json'))
    if (attempt/'capacity-prefix-proof.json').exists():
        shutil.copyfile(attempt/'capacity-prefix-proof.json',directory/'capacity-prefix-proof.json')
    save(directory/'receipt.json', receipt)
    shutil.copyfile(attempt/'stdout.txt', directory/'stdout.txt')
    directory.rename(dest)
    # The small outer attempt receipt remains ignored as a crash/recovery breadcrumb.
    refresh()
    save(HERE/'status.json', dict(status='prompt-verified', prompt=prompt, updated_utc=utc()))
    print(prompt + ': verified', flush=True)

def refresh():
    entries=[]
    for row in read(PROMPTS)['prompts']:
        prompt=row['id']; d=HERE/prompt; bundle=OLD_INPUTS/prompt
        if not (d/'receipt.json').exists():continue
        r,result=read(d/'receipt.json'),read(d/'result.json')
        if not r.get('verified'):continue
        entries.append(dict(prompt_id=prompt,prompt_tokens=r['prompt_tokens'],
            input_bundle=str(bundle.relative_to(ROOT)),
            input_bundle_hashes={f.name:sha(f) for f in sorted(bundle.iterdir()) if f.is_file()},
            oracle_directory=str(d.relative_to(ROOT)),oracle_receipt_sha256=sha(d/'receipt.json'),
            generated_tokens=len(result['tokens']),first_8_token_ids=result['tokens'][:8],last_8_token_ids=result['tokens'][-8:],
            ended_early=len(result['tokens'])<128,termination=result['status'],context=256,
            fixture_steps=fixture_steps(len(result['tokens'])),
            mean_seconds_per_position=r['mean_seconds_per_position'],
            elapsed_seconds=r['elapsed_seconds'],cpu_seconds=r['cpu_seconds'],
            suite64_equality=read(d/'suite64-equality-proof.json')['passed']))
    manifest=dict(schema='own-runtime.iq3.suite-inputs.v1',arithmetic='iq3-p17-detmath-v2',context=256,token_cap=128,
        suite_sha256=read(PROMPTS)['suite_sha256'],prompts_manifest_sha256=sha(PROMPTS),complete=len(entries)==12,prompts=entries,
        total_elapsed_seconds=sum(e['elapsed_seconds'] for e in entries),
        total_cpu_hours=sum(e['cpu_seconds'] or 0 for e in entries)/3600,
        cpu_accounting_complete=all(e['cpu_seconds'] is not None for e in entries))
    save(INPUTS/'suite-manifest.json',manifest)
    table='| Prompt | Prompt tokens | Generated | Early end | First 8 token IDs | Last 8 token IDs | Seconds/position | 64-prefix equal |\n| --- | ---: | ---: | --- | --- | --- | ---: | --- |\n'
    for e in entries:
        table+=f"| {e['prompt_id']} | {e['prompt_tokens']} | {e['generated_tokens']} | {e['ended_early']} | {', '.join(map(str,e['first_8_token_ids']))} | {', '.join(map(str,e['last_8_token_ids']))} | {e['mean_seconds_per_position']:.4f} | {e['suite64_equality']} |\n"
    text=f"""# Arithmetic-v2 128-token CPU suite

Verified prompts: {len(entries)}/12. Complete: {manifest['complete']}.
Arithmetic `iq3-p17-detmath-v2`, quantized Unsloth UD-IQ3_XXS; context 256; cap 128.
EOS 248044 or 248046 is included and then stops generation; no forced continuation.

{table}
Numerical-process wall time (sum): {manifest['total_elapsed_seconds']:.3f} seconds.
Measured user + system CPU time: {manifest['total_cpu_hours']:.6f} CPU hours.
Per-position wall times are in `positions.jsonl`; per-generated-token times and IDs are
in `tokens.jsonl`; decoded text is in `result.json`. Token 1 includes prefill time.
These are CPU oracle costs, not serving speeds.

Capacity changes only allocated cache extents and guards, not valid-position arithmetic.
See `capacity-analysis.md` in the oracle directory for source evidence. Before token 65,
the incident run must reproduce the sealed 64 tokens, all 64 logit/top-five records,
384 BF16 layer fixtures and 8 ledgers byte for byte at context 256. Other prompts cannot
start until this incident result is sealed. Each prompt's `suite64-equality-proof.json`
compares the finished 64-token suite when available; any difference stops the campaign.
The source analysis predicts comparable prefixes; measured confirmation is {'PASS' if (HERE/'incident-retrospective/equality-proof.json').exists() else 'PENDING'}.

The sealed program hard-codes cap 64/context 192: `oracle128.patch` changes only those
limits, captures steps 97–104 as well as 1–8, and adds the prefix checkpoint wait.
All numerical sources and compiler flags are unchanged and hash-bound in
`build-receipt.json`; the rebuilt binary has its own hash. No device code is run.

Input bundles do not depend on generation cap or context. Packet29 `prepare.py` takes
only the prompt, so each new input directory holds `bundle-reference.json`, binding
all five existing bundle files by SHA256 without duplicating them. Use the manifest's
`input_bundle` for window.py `--input`; the native runtime takes its `tokens.txt`.

Two OpenMP threads per oracle. While the existing suite runs, only one new oracle runs;
after it exits, at most three run, within the 12-thread ceiling. CPU affinity is inherited,
nice 19 and idle I/O are required. Combined oracle anonymous memory is guarded below
11 GB; each new worker below 3 GB. No sudo, devices, host settings, or model writes.
`df -B1 /` guards large writes and runs every ten seconds; below 8 GB stops work.
Scratch stays below 2 GB. Retain raw 20,480-byte BF16 fixtures only for steps 1–8 and
97–104 (through EOG). Compress progress/timing logs with deterministic gzip, verify
restored hashes before deleting raw logs; original hashes/sizes are in receipts.
Large teardown and compressed evidence files are necessary receipts, not disposable dumps.
No models or executable build files are committed; `build_cpu.py` recreates the CPU binary.

Each prompt runs under a private temporary name, is verified, then renamed. Finished
prompts are reverified and skipped on restart; completed partial results are recovered.
An interrupted unfinished prompt alone needs recomputation. `status.json` and each
attempt's status update after each position. Failed runs are not retried automatically.
The coordinator was corrected after the first two prompts: its old-suite process check
matched the new suite128 directory as a text prefix. It now compares path components.
Both finished prompts were pushed before the supervisor was stopped; neither was rerun.
See `coordination-fix.json`; this changed process admission only, not oracle arithmetic.

Each finished prompt gets a separate explicit-path commit and push, with the requested
coauthor. Fetch/merge main on remote movement; no stash, branches or rebase.

Run from repository root:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 -B {HERE.relative_to(ROOT)}/build_cpu.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 -B {HERE.relative_to(ROOT)}/suite_run.py --all --jobs 3 --publish
nice -n 19 ionice -c 3 python3 -B {HERE.relative_to(ROOT)}/suite_check.py {HERE.relative_to(ROOT)}
```

The checker accepts prompt directories or prompt/run directories and verifies both
fixture ranges and the complete 128-token sequence (or recorded EOG). Unit tests use
oracle files and corrupted copies, including tail corruption. This extends exactness
coverage past token 100; it is not a 512-token final performance gate or a speed result.
"""
    for root in (HERE,INPUTS):
        temporary=root/'README.md.tmp';temporary.write_text(text)
        check(temporary.read_text()==text,'README verification');temporary.replace(root/'README.md')

def publish(prompt):
    def git(*args):
        return subprocess.check_output(PREFIX+['git', '-c', 'pack.threads=1', '-c', 'index.threads=1', '-c', 'gc.auto=0', *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT)
    check(git('branch','--show-current').strip() == 'main', 'main only')
    check(not git('diff','--cached','--name-only').strip(), 'unrelated staged files; do not commit')
    paths = [HERE/'build_cpu.py', HERE/'build-receipt.json', HERE/'oracle128.cpp', HERE/'oracle128.patch', HERE/'capacity-analysis.md', HERE/prompt, INPUTS/prompt, HERE/'suite_run.py', HERE/'runner-snapshots', HERE/'.gitignore', HERE/'README.md', INPUTS/'.gitignore', INPUTS/'README.md', INPUTS/'suite-manifest.json']
    for name in ('suite_check.py', 'test_suite_check.py', 'test_suite_run.py', 'checker-tests.json', 'resume-cleanup.json', 'resume-audit.json', 'resume_verify.py', 'coordination-fix.json', 'verify_completed.py'):
        if (HERE/name).exists(): paths.append(HERE/name)
    paths = [str(p.relative_to(ROOT)) for p in paths]
    git('add','--',*paths)
    git('diff','--cached','--check')
    if git('diff','--cached','--name-only').strip():
        print(git('commit','--quiet','-m',f'Add verified arithmetic-v2 suite oracle: {prompt}','-m','Co-Authored-By: Codex <noreply@openai.com>','--',*paths), flush=True)
    git('fetch','origin','main')
    if subprocess.call(PREFIX+['git','merge-base','--is-ancestor','origin/main','HEAD'],cwd=ROOT) != 0:
        print(git('diff','--stat','HEAD...origin/main'), flush=True)
        print(git('merge','--no-edit','-m','Merge origin/main for suite128 receipts\n\nCo-Authored-By: Codex <noreply@openai.com>','origin/main'), flush=True)
    print(git('push','origin','HEAD:main'), flush=True)

def oracle_processes():
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            args=(p/'cmdline').read_bytes().split(b'\0')
            if args and args[0].endswith(b'/oracle'):
                st=(p/'status').read_text().splitlines()
                anon=next(int(x.split()[1])*1024 for x in st if x.startswith('RssAnon:'))
                found.append(dict(pid=int(p.name),anon=anon,args=args))
        except (OSError,StopIteration):pass
    return found

def oracle_belongs_to(directory, record):
    args=record['args']
    return len(args)>2 and Path(args[2].decode()).is_relative_to(directory)

def old_suite_running():
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            args=(p/'cmdline').read_bytes().split(b'\0')
            if any(x.decode(errors='replace').endswith(str(OLD.relative_to(ROOT))+'/suite_run.py') for x in args):return True
        except OSError:pass
    return any(oracle_belongs_to(OLD,p) for p in oracle_processes())

def parallel_worker(row, sealed, binary, affinity, results):
    try:
        result = run_prompt(row, sealed, binary, affinity, defer_finalize=True)
        results.put((row['id'], True, result))
    except BaseException as error:
        results.put((row['id'], False, repr(error)))

def remaining_parallel(selected, sealed, binary, affinity, publish_results):
    # Two independent frozen two-thread CPU programs; parent alone seals and commits.
    ctx = multiprocessing.get_context('fork')
    results = ctx.Queue()
    active = {}
    pending = list(selected)
    def stop_all(sig, frame):
        raise RuntimeError('suite interrupted; stopping CPU children cooperatively')
    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)
    try:
        while pending or active:
            while pending and len(active) < (1 if old_suite_running() else 3):
                row = pending.pop(0)
                disk_guard()
                child = ctx.Process(target=parallel_worker, args=(row,sealed,binary,affinity,results))
                child.start()
                active[row['id']] = child
            try:
                prompt, passed, payload = results.get(timeout=5)
            except queue.Empty:
                check(all(c.is_alive() for c in active.values()), 'CPU worker exited without a result')
                continue
            child = active.pop(prompt)
            child.join(timeout=60)
            check(passed and child.exitcode==0, 'CPU worker failed: '+str(payload))
            finalize_prompt(*payload)
            if publish_results:
                publish(prompt)
    finally:
        for child in active.values():
            if child.is_alive():
                child.terminate()  # worker forwards SIGTERM to its one CPU oracle
        for child in active.values():
            child.join(timeout=60)
        results.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--publish', action='store_true')
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--jobs', type=int, choices=(1,3), default=1)
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
        # Check all retained independent CPU token lists before the remaining coverage.
        if args.all:
            priority = ['incident-retrospective']
            selected.sort(key=lambda row: priority.index(row['id']) if row['id'] in priority else 4)
        remaining = []
        for row in selected:
            if args.jobs==3 and row['id'] != 'incident-retrospective' and not (HERE/row['id']).exists():
                remaining.append(row)
                continue
            check(not (HERE/'STOP-disagreement.json').exists(), 'CPU disagreement latch present')
            run_prompt(row, sealed, binary, affinity)
            if args.publish:
                publish(row['id'])
        if remaining:
            remaining_parallel(remaining,sealed,binary,affinity,args.publish)
        save(HERE/'status.json', dict(status='selected-prompts-complete', updated_utc=utc()))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        save(HERE/'status.json', dict(status='stopped', error=str(error), updated_utc=utc()))
        raise
