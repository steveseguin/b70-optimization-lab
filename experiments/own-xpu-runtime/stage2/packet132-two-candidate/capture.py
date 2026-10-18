#!/usr/bin/env python3
"""CPU-only independent-text target/draft capture; no device APIs or services.

Run with nice -n 19 taskset -c 8-15,24-31 python3 -B capture.py ROOT </dev/null.
The supervisor runs one bounded child at a time, including build and draft.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
REPO = P.parents[3]
STAGE = P.parent
LANE = REPO / 'experiments/qwen38-flash-next-ud-iq3xxs-b70'
OLD = Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/build')
AUTH = STAGE / 'packet49c-round2/build/input'
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python3'
PREFIX = 80128
CAP = 24
EXCERPT = 16


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def policy():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert not sys.stdin.isatty()
    # Address-space cap also bounds anonymous resident allocation. Native oracle
    # lowers this to 5 GB. The small supervisor and one child remain below 8 GB.
    resource.setrlimit(resource.RLIMIT_AS, (7_500_000_000, 7_500_000_000))


def process_rss(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                return int(line.split()[1]) * 1024
    except FileNotFoundError:
        pass
    return 0


def run(command, log, timeout, env=None):
    started = time.monotonic()
    peak = 0
    failure = None
    with log.open('w') as output:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output,
                                 stderr=subprocess.STDOUT, env=env)
        try:
            while child.poll() is None:
                peak = max(peak, process_rss(os.getpid()) + process_rss(child.pid))
                if peak >= 7_800_000_000:
                    raise RuntimeError('aggregate parent/child RSS reached 7.8 GB')
                if time.monotonic() - started > timeout:
                    raise RuntimeError('bounded stage timed out; no retries')
                time.sleep(0.5)
        except BaseException as exc:
            failure = exc
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()  # CPU-only child; never a GPU process.
                child.wait()
    result = dict(command=list(map(str, command)), returncode=child.returncode,
                  wall_seconds=time.monotonic()-started,
                  sampled_parent_child_peak_rss_bytes=peak)
    if failure is not None:
        result['exception'] = repr(failure)
    dump(log.with_suffix('.receipt.json'), result)
    if failure is not None:
        raise failure
    if child.returncode:
        raise RuntimeError(f'CPU stage failed; see {log}')
    return result


def prepare(root):
    """Headers and frozen independent documents only; never benchmark payloads."""
    sys.path.insert(0, str(REPO / 'experiments/own-xpu-runtime/stage1/packet1b'))
    sys.path.insert(0, str(LANE / 'packet2-cpu-oracle'))
    from loaders.headers import gguf_header
    from tokenizer import Tokenizer
    authority = json.loads((AUTH / 'input.json').read_text())
    model = Path(authority['model_dir'])
    for line in (AUTH / 'identity.tsv').read_text().splitlines():
        name, *identity = line.split()
        s = (model / name).stat()
        assert (s.st_size, s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns) == tuple(map(int, identity))
    shard = next(model.glob('*00001-of-00003.gguf'))
    with shard.open('rb') as stream:
        header = gguf_header(stream, shard.stat().st_size)
        stream.seek(0)
        assert sha(stream.read(header['header_bytes_read'])) == authority['header_sha256']
    tokenizer = Tokenizer(header['metadata'])
    rule_path = next(STAGE.glob('packet114*/calibration/preregistration.json'))
    rule = json.loads(rule_path.read_text())
    sources = []
    for index, entry in enumerate(rule['sources']):
        raw = subprocess.check_output(['git', 'show', rule['source_commit']+':'+entry['path']],
                                      cwd=REPO, stdin=subprocess.DEVNULL)
        assert sha(raw) == entry['sha256'] and len(raw) == entry['bytes']
        tokens = tokenizer.encode(raw.decode())
        assert tokenizer.decode(tokens) == raw.decode()
        start = len(tokens)//2
        ids = tokens[start:start+EXCERPT]
        assert len(ids) == EXCERPT
        directory = root / f'doc-{index}/input'
        directory.mkdir(parents=True)
        for name in ('plan.tsv', 'identity.tsv'):
            shutil.copyfile(AUTH/name, directory/name)
        (directory/'tokens.txt').write_text(' '.join(map(str, ids))+'\n')
        record = dict(entry, source_commit=rule['source_commit'], document_index=index,
                      full_token_count=len(tokens), excerpt_start=start, tokens=ids,
                      excerpt_text=tokenizer.decode(ids), model_dir=str(model),
                      header_sha256=authority['header_sha256'], chat_template=False,
                      generated_token_cap=CAP)
        dump(directory/'input.json', record)
        sources.append(record)
    dump(root/'inputs.json', dict(schema='packet132.independent-inputs.v1', sources=sources,
                                 preregistration_sha256=sha(rule_path.read_bytes())))


def build(root):
    original = json.loads((STAGE/'packet49-integrate/oracle/build-receipt.json').read_text())
    directory = root/'build'
    src = directory/'src'
    src.mkdir(parents=True)
    for name, expected in original['generated_sources'].items():
        raw = (OLD/'src'/name).read_bytes()
        assert sha(raw) == expected, name
        (src/name).write_bytes(raw)
    oracle = (src/'oracle.cpp').read_text()
    edits = [("38'000'000'000ull", "5'000'000'000ull"),
             ('a.context=4096;', 'a.context=128;')]
    for before, after in edits:
        assert before in oracle
        oracle = oracle.replace(before, after)
    # Capture only final streams already instrumented by packet49; expensive
    # layer dumps are unnecessary here. This alters logging, not arithmetic.
    before = 'if(capture>0 && (capture<=8 || (capture>=97 && capture<=104)))'
    assert before in oracle
    oracle = oracle.replace(before, 'if(false)')
    (src/'oracle.cpp').write_text(oracle)
    command = [arg.replace(str(OLD), str(directory)) for arg in original['command']]
    run(command, root/'build-oracle.log', 300)
    matmul = LANE/'packet3-runtime-oracle/matmul.cpp'
    command2 = ['g++', '-std=c++20', '-O2', '-mfma', '-fno-fast-math',
                '-ffp-contract=off', '-shared', '-fPIC', str(matmul), '-o', str(directory/'matmul.so')]
    run(command2, root/'build-matmul.log', 120)
    dependencies = subprocess.check_output(['g++', '-std=c++20', '-MM', str(matmul)],
                                          text=True, stdin=subprocess.DEVNULL)
    dependency_files = dependencies.replace('\\\n', ' ').split(':', 1)[1].split()
    matmul_dependencies = {str(Path(name).resolve().relative_to(REPO)):sha(Path(name).read_bytes())
                           for name in dependency_files}
    deps = subprocess.check_output(['readelf', '-d', directory/'oracle'], text=True,
                                   stdin=subprocess.DEVNULL)
    assert not any(x in deps.lower() for x in ('libsycl', 'libze_loader', 'libur_loader'))
    dump(root/'build-receipt.json', dict(schema='packet132.cpu-build.v1', device_executed=False,
          original_receipt_sha256=sha((STAGE/'packet49-integrate/oracle/build-receipt.json').read_bytes()),
          source_changes='5 GB address cap; context 128; suppress per-layer debug dumps; arithmetic unchanged',
          sources={p.name:sha(p.read_bytes()) for p in src.iterdir()},
          oracle_sha256=sha((directory/'oracle').read_bytes()),
          matmul_source_sha256=sha(matmul.read_bytes()),
          matmul_dependency_sha256=matmul_dependencies,
          matmul_sha256=sha((directory/'matmul.so').read_bytes()),
          commands=[command, command2], dependencies=deps))


def draft(root, index):
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    sys.path.insert(0, str(STAGE/'packet31-mtp-acceptance'))
    import draft_reference as ref
    directory = root/f'doc-{index}'
    info = json.loads((directory/'input/input.json').read_text())
    target = json.loads((directory/'target/result.json').read_text())
    assert target['status'] in ('token-cap', 'eos') and not target['device_executed']
    tokens = info['tokens'] + target['tokens']
    store = ref.SafeStore()
    bindings = ref.Bindings.__new__(ref.Bindings)
    bindings.iq = ref.RecordedStore()
    bindings.s = store
    bindings.head = ref.IQLinear(ref.Library(root/'build/matmul.so'), bindings.iq, 'output.weight')
    bindings.head.n = PREFIX
    bindings.coarse = None
    model = ref.Draft(store, expanded=True)
    count = 0
    with torch.inference_mode(), (directory/'draft-rows.jsonl').open('w') as output:
        for position in range(len(tokens)-2):
            raw = (directory/f'target/capture-streams/streams-{position}.bf16').read_bytes()
            assert len(raw) == 4*2560*2
            hidden = torch.frombuffer(bytearray(raw), dtype=torch.bfloat16).reshape(1,4,2560)
            sample = model(hidden, bindings.embedding(tokens[position+1]), position)
            # Populate draft attention state for every prefix position; collect
            # heads only where a newly generated target label is available.
            if position < len(info['tokens'])-2:
                continue
            logits = bindings.logits(sample)
            order = torch.argsort(logits, descending=True, stable=True)[:2]
            prob = torch.softmax(logits, dim=0)
            ids = order.tolist()
            target_index = position-(len(info['tokens'])-2)
            label = target['tokens'][target_index]
            row = dict(document_index=index, source_index=index+1, prompt_id=f'source-{index+1}',
                       generated_index=target_index, top1=ids[0], top2=ids[1],
                       margin=float(logits[order[0]]-logits[order[1]]),
                       prefix_probability=float(prob[order[0]]), source_path=info['path'], position=position,
                       generated_target_index=target_index, next_input_token=tokens[position+1],
                       target_token=label, draft_top2=ids,
                       top2_logits=logits[order].tolist(), top2_probabilities=prob[order].tolist(),
                       top1_probability=float(prob[order[0]]),
                       probability_margin=float(prob[order[0]]-prob[order[1]]),
                       logit_margin=float(logits[order[0]]-logits[order[1]]),
                       top1_hit=ids[0]==label, second_hit=ids[1]==label,
                       stream_sha256=sha(raw), draft_prefix_rows=PREFIX,
                       arithmetic_scope='packet31 CPU expanded INT8 draft; not device-bit parity')
            output.write(json.dumps(row, allow_nan=False)+'\n')
            output.flush()
            count += 1
            print(f'doc {index} captured {count}', flush=True)
    assert count == len(target['tokens'])
    dump(directory/'draft-receipt.json', dict(count=count, device_executed=False,
          max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          draft_source_sha256=sha((STAGE/'packet31-mtp-acceptance/draft_reference.py').read_bytes()),
          official_read_receipts=store.receipt, iq_read_receipts=bindings.iq.read_receipt))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--phase', choices=('all','prepare','draft'), default='all')
    parser.add_argument('--document', type=int)
    args = parser.parse_args()
    policy()
    root = args.root.resolve()
    if args.phase == 'prepare':
        prepare(root)
        return
    if args.phase == 'draft':
        draft(root, args.document)
        return
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
               PYTHONDONTWRITEBYTECODE='1', P49_CAPTURE='1', MALLOC_ARENA_MAX='2')
    env.pop('IQ3_PREFIX_GATE', None)
    run([PYTHON, '-B', str(P/'capture.py'), str(root), '--phase', 'prepare'], root/'prepare.log', 120, env)
    build(root)
    inputs = json.loads((root/'inputs.json').read_text())
    env['IQ3_MODEL_DIR'] = inputs['sources'][0]['model_dir']
    for index in range(len(inputs['sources'])):
        assert time.monotonic()-started < 4200, 'whole capture budget exhausted'
        directory = root/f'doc-{index}'
        run([str(root/'build/oracle'), str(directory/'input'), str(directory/'target'), '840', str(CAP)],
            directory/'target.log', min(880, 4200-(time.monotonic()-started)), env)
        run([PYTHON, '-B', str(P/'capture.py'), str(root), '--phase', 'draft', '--document', str(index)],
            directory/'draft.log', min(300, 4200-(time.monotonic()-started)), env)
    rows = ''.join((root/f'doc-{i}/draft-rows.jsonl').read_text() for i in range(len(inputs['sources'])))
    (root/'rows.jsonl').write_text(rows)
    dump(root/'rows.json', [json.loads(line) for line in rows.splitlines()])
    dump(root/'completion.json', dict(schema='packet132.capture-complete.v1',
          wall_seconds=time.monotonic()-started, rows=len(rows.splitlines()),
          rows_sha256=sha(rows.encode()), device_executed=False,
          incidental_metadata_exposure='During harness inspection, existing packet49c input.json token IDs were displayed with model/header metadata. No benchmark prompt text or output was opened; none used in calibration or threshold choice.',
          max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))


if __name__ == '__main__':
    main()
