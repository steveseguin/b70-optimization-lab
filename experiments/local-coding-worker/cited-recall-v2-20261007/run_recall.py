#!/usr/bin/env python3
"""One preregistered references-only recall request; no tools, retry or repair."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PILOT = Path('/home/steve/worker-cited-recall-v2-20261007')
COMPILER = HERE / 'compile_citations.py'
WIRE = ROOT / 'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py'
VALIDATOR = HERE.parent / 'evaluation-20261007/memory/validate.py'
SYSTEM = (HERE / 'evaluation/model-input/instructions.txt').read_bytes().decode('utf-8')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compiler = load_module('recall_citation_compiler', COMPILER)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def messages_for(bundle):
    compiler.validate_bundle(bundle)
    if len(bundle['questions']) != 10 or set(bundle['corpus']) != {'S01', 'S02', 'S03', 'S04'}:
        raise ValueError('Expected all ten questions and all four complete documents')
    parts = []
    for doc_id, text in sorted(bundle['corpus'].items()):
        lines = '\n'.join(f'{number:04d} | {line}' for number, line in enumerate(text.splitlines(), 1))
        parts.append(f'DOCUMENT {doc_id}\n{lines}\nEND DOCUMENT {doc_id}')
    parts.append(json.dumps({'questions': bundle['questions']}, ensure_ascii=False, indent=2))
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': '\n\n'.join(parts)}]


def save(path, value):
    data = value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def sync_tree(root):
    for path in root.rglob('*'):
        if path.is_file():
            with path.open('rb') as stream: os.fsync(stream.fileno())
    for path in sorted([p for p in root.rglob('*') if p.is_dir()], key=lambda p: len(p.parts), reverse=True) + [root, root.parent]:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def healthy(state):
    if any((state / name).exists() for name in ('STOP', 'FAULT.json', 'shutdown.json')):
        raise RuntimeError('Server stopped, stopping or faulted')


def server_identity(state):
    healthy(state)
    if json.loads((state.parent / 'boundaries/result.json').read_text()).get('status') != 'passed':
        raise RuntimeError('Boundary gate has not passed')
    pid = json.loads((state / 'pid.json').read_text())['supervisor_pid']
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    age = float(Path('/proc/uptime').read_text().split()[0]) - int(fields[19]) / os.sysconf('SC_CLK_TCK')
    if age < 0 or age > 1200 - 480:
        raise RuntimeError('Fewer than 480 seconds remain in the original supervisor budget')
    return {'supervisor_pid': pid, 'supervisor_age_seconds': age,
            'container': json.loads((state / 'container.json').read_text())}


def make_model(profile, directory):
    sys.path.insert(0, str(ROOT / 'worker'))
    from model import LocalModel
    return LocalModel(profile['base_url'], profile['model'], directory,
                      profile['max_input_tokens'], profile['max_output_tokens'],
                      generation=profile['generation'])


def deadline(signum, frame):
    raise TimeoutError('Recall exceeded its 420-second total network budget')


def terminated(signum, frame):
    raise InterruptedError('Recall interrupted by SIGTERM; no retry')


def run_trial():
    state, out = PILOT / 'server', PILOT / 'recall'
    # A duplicate invocation cannot overwrite evidence or stop another lock owner.
    with open('/tmp/neural-local-worker.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(exist_ok=False)
        result = {'schema': 'lab.cited-recall.trial.v2', 'status': 'failed', 'model_requests': 0,
                  'semantic_grading': 'not-performed', 'model_quality_result': False,
                  'started_epoch_s': time.time(), 'runner_sha256': digest(Path(__file__).read_bytes())}
        previous_handler = None
        previous_term_handler = None
        try:
            previous_term_handler = signal.signal(signal.SIGTERM, terminated)
            healthy(state)
            protocol_bytes = (HERE / 'trial-protocol.json').read_bytes()
            profile_bytes = (HERE / 'request-profile.json').read_bytes()
            source_bytes = (HERE / 'evaluation/model-input/source-bundle.json').read_bytes()
            instructions_bytes = (HERE / 'evaluation/model-input/instructions.txt').read_bytes()
            protocol = compiler.strict_json(protocol_bytes)
            profile = compiler.strict_json(profile_bytes)
            inputs = {'source_bundle_sha256': digest(source_bytes), 'instructions_sha256': digest(instructions_bytes),
                      'request_profile_sha256': digest(profile_bytes),
                      'compiler_sha256': digest(COMPILER.read_bytes()), 'wire_sha256': digest(WIRE.read_bytes()),
                      'validator_sha256': digest(VALIDATOR.read_bytes())}
            result.update(protocol_sha256=digest(protocol_bytes), **inputs)
            if any(protocol.get(name) != value for name, value in inputs.items()):
                raise ValueError('Frozen source/profile/compiler/wire identity mismatch')
            if instructions_bytes.decode('utf-8') != SYSTEM:
                raise ValueError('Loaded SYSTEM differs from frozen packet instructions')
            if protocol.get('runner_sha256', result['runner_sha256']) != result['runner_sha256']:
                raise ValueError('Frozen runner identity mismatch')
            bundle = compiler.strict_json(source_bytes)
            messages = messages_for(bundle)
            prompt_hash = digest(json.dumps(messages, ensure_ascii=False, separators=(',', ':')).encode())
            result['messages_sha256'] = prompt_hash
            if prompt_hash != protocol['messages_sha256']:
                raise ValueError('Frozen prompt identity mismatch')
            if (profile['max_input_tokens'] != 28000 or profile['max_output_tokens'] != 3072
                    or profile['generation'] != {'temperature': 0, 'top_p': 1, 'seed': 42}):
                raise ValueError('Unexpected frozen request limits or sampling')
            expected = protocol['expected_input_tokens']
            if type(expected) is not int or not 300 < expected <= 28000 or expected + 3072 > 33024:
                raise ValueError('Frozen input token count exceeds the admitted bounds')
            for name, data in [('source-bundle.json', source_bytes), ('request-profile.json', profile_bytes),
                               ('instructions.txt', instructions_bytes), ('trial-protocol.json', protocol_bytes),
                               ('prompt.json', messages)]: save(out / name, data)
            result['server_identity'] = server_identity(state)
            if 'supervisor_sha256' in protocol:
                launch_bytes = (state / 'launch.json').read_bytes()
                launch = compiler.strict_json(launch_bytes)
                if (digest((HERE / 'serve_r276_once.py').read_bytes()) != protocol['supervisor_sha256']
                        or launch.get('supervisor_sha256') != protocol['supervisor_sha256']):
                    raise ValueError('Frozen serving supervisor identity mismatch')
                result['server_identity']['launch_sha256'] = digest(launch_bytes)
                result['server_identity']['supervisor_sha256'] = protocol['supervisor_sha256']
            model = make_model(profile, out / 'requests')
            if model.thinking: raise ValueError('This trial requires nonthinking generation')
            previous_handler = signal.signal(signal.SIGALRM, deadline); signal.alarm(420)
            healthy(state)
            with model.fetch('/tokenize', {'model': model.model, 'messages': messages,
                    'add_generation_prompt': True, 'chat_template_kwargs': model.template_kwargs}) as response:
                count = json.load(response)['count']
            save(out / 'token-count.json', {'input_tokens': count, 'expected_input_tokens': expected,
                                           'maximum_output': 3072, 'context_limit': 33024})
            if type(count) is not int or count != expected:
                raise ValueError('CPU/server token counts disagree; no generation')
            request = model.out / '001'; request.mkdir()
            payload = {'model': model.model, 'messages': messages, **model.sampling, 'max_tokens': 3072,
                       'n': 1, 'stream': True, 'stream_options': {'include_usage': True},
                       'return_token_ids': True, 'chat_template_kwargs': model.template_kwargs}
            with model.fetch('/metrics') as response: before = response.read().decode()
            save(request / 'metrics-before.txt', before.encode())
            healthy(state)
            result['model_requests'] = 1
            response = model.wire.request_one(model.base, payload, request,
                                             opener=model.opener.open, timeout_seconds=420)
            save(request / 'response.json', response)
            if (response['prompt_tokens'] != count or type(response['cached_tokens']) is not int
                    or response['cached_tokens'] != 0 or response.get('finish_reasons') != ['stop']
                    or response.get('token_ids_available') is not True
                    or len(response['token_ids']) != response['completion_tokens']):
                raise ValueError('Strict response token/cache/completion identity failed')
            healthy(state)
            with model.fetch('/metrics') as stream: after = stream.read().decode()
            save(request / 'metrics-after.txt', after.encode())
            save(request / 'metric-delta.json', model.metrics_wire.metric_delta(before, after, count))
            signal.alarm(0)
            raw = response['text'].encode('utf-8')
            save(out / 'raw-refs.json', raw)
            refs = compiler.strict_json(raw)
            compiler.compile_references(refs, [q['id'] for q in bundle['questions']], bundle['corpus'])
            if any(len(answer['citations']) > 2 for answer in refs['answers']):
                raise ValueError('More than two citations in an answer; no repair')
            compilation = compiler.compile_files(out / 'source-bundle.json', out / 'raw-refs.json', out / 'compiled')
            validator_hash = digest(VALIDATOR.read_bytes())
            if validator_hash != inputs['validator_sha256']:
                raise ValueError('Frozen original validator changed during the request')
            validator = load_module('recall_original_validator', VALIDATOR)
            compiled = compiler.strict_json((out / 'compiled/compiled.json').read_bytes())
            validator.check_responses(compiled, bundle['questions'], bundle['corpus'])
            save(out / 'mechanical-crosscheck.json', {'status': 'passed', 'validator_sha256': validator_hash,
                  'function': 'check_responses', 'fresh_questions_only': True, 'semantic_grading': 'not-performed'})
            result.update(status='complete-awaiting-semantic-review', semantic_grading='pending-independent-review',
                          raw_refs_sha256=digest(raw), compiled_sha256=compilation['compiled_sha256'])
        except (Exception, KeyboardInterrupt) as error:
            result['error'] = f'{type(error).__name__}: {error}'
        finally:
            signal.alarm(0)
            if previous_handler is not None: signal.signal(signal.SIGALRM, previous_handler)
            if previous_term_handler is not None: signal.signal(signal.SIGTERM, previous_term_handler)
            if state.is_dir():
                try: save(state / 'STOP', b'One-shot recall complete or failed; no retry.\n')
                except FileExistsError: pass
            result['finished_epoch_s'] = time.time()
            save(out / 'result.json', result)
            sync_tree(out)
            if state.is_dir():
                fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY)
                try: os.fsync(fd)
                finally: os.close(fd)
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'complete-awaiting-semantic-review' else 1


if __name__ == '__main__':
    raise SystemExit(run_trial())
