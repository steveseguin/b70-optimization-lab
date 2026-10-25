#!/usr/bin/env python3
"""Run the canonical suite against an already-running depth-3 probe service.

No launch, reload, or recovery actions. Each validated HTTP response is bound
to its native request/result and copied before another suite request runs.
Use --evidence-dir NEW_DIR plus the normal suite --label/--out arguments.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUITE_PATH = ROOT / 'experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/run_suite.py'
CURRENT = Path.home() / 'own-xpu-runtime-results/sc117-lan/current'
EXPECTED = {'OWNRT_DRAFT_DEPTH_PROBE': '3', 'OWNRT_DRAFT_DEPTH_VERIFY': '1', 'OWNRT_EARLY_RANK1': '0'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    s = path.stat()
    return {'path': str(path), 'device': s.st_dev, 'inode': s.st_ino}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    with path.open('x') as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


class Capture:
    def __init__(self, evidence_dir, current=CURRENT):
        self.current = current
        require(current.is_symlink(), 'current must be a service control symlink')
        self.control = current.resolve(strict=True)
        self.control_identity = identity(self.control)
        self.plan_bytes = (self.control / 'plan.json').read_bytes()
        self.plan = json.loads(self.plan_bytes)
        environments = self.plan['environment']
        require(isinstance(environments, list) and len(environments) == 2, 'two rank environments required')
        for env in environments:
            require(all(env.get(k) == v for k, v in EXPECTED.items()), 'required explicit depth-probe flags do not match')
        require(self.plan.get('mini') is False, 'real-model service plan required')
        require(isinstance(self.plan.get('binary_sha256'), str) and len(self.plan['binary_sha256']) == 64,
                'binary identity required')
        self.ranks = Path(self.plan['output'])
        require(self.ranks == self.control / 'ranks', 'unexpected native control directory')
        self.runtime_evidence = Path(self.plan['evidence_output'])
        require(self.runtime_evidence.is_absolute(), 'absolute evidence_output required')
        self.destination = Path(evidence_dir).absolute()
        self.destination.mkdir(parents=True, exist_ok=False)
        (self.destination / 'plan.json').write_bytes(self.plan_bytes)
        save_json(self.destination / 'service-identity.json', {
            'control': self.control_identity, 'current_symlink': str(current),
            'plan_sha256': sha(self.plan_bytes), 'binary_sha256': self.plan['binary_sha256'],
            'required_environment': EXPECTED,
            'native_result_mapping': 'rank.hpp writes and adapter6 reads plan.output/native-result.json; retained copy is per-prompt rank0/native-result.json',
            'scope': 'instrumented depth-probe evidence; not a performance qualification'})
        self.last_request = None

    def check_control(self):
        require(self.current.resolve(strict=True) == self.control, 'service current changed during suite')
        require(identity(self.control) == self.control_identity, 'service control directory identity changed')
        require((self.control / 'plan.json').read_bytes() == self.plan_bytes, 'service plan changed during suite')

    def __call__(self, row, response):
        self.check_control()
        request_log = self.control / 'requests.jsonl'
        log_bytes = request_log.read_bytes()
        lines = log_bytes.splitlines()
        require(bool(lines) and log_bytes.endswith(b'\n'), 'request log empty or incomplete')
        latest = json.loads(lines[-1])
        number = response['ownrt']['request']
        require(type(number) is int and number > 0 and latest['request'] == number, 'HTTP/latest request identity mismatch')
        require(self.last_request is None or number > self.last_request, 'request index did not advance')
        for k in ('prompt_tokens', 'output_tokens'):
            require(latest[k] == row[k] == response['ownrt'][k], k + ' differs between HTTP and request log')
        require(latest.get('continued_from') == 0 and row['cached_tokens'] == 0, 'probe request must be fresh')
        config_path = self.ranks / 'native-request.txt'
        config_bytes = config_path.read_bytes()
        config = config_bytes.decode().split()
        require(len(config) >= 7, 'truncated native request')
        mode, cap, overlap, dumps, np, ns, ne = map(int, config[:7])
        require(mode == 3 and cap == 512 and np == row['prompt_tokens'], 'native request mode/cap/prompt count mismatch')
        require(list(map(int, config[7:7 + np])) == row['prompt_token_ids'], 'native prompt ids differ from HTTP suite')
        require('start' not in config[7 + np + ns + ne:], 'native continuation request refused')
        native_path = self.ranks / 'native-result.json'
        native_bytes = native_path.read_bytes()
        native = json.loads(native_bytes)
        require(isinstance(row['output_token_ids'], list) and native['tokens'] == row['output_token_ids'],
                'native/HTTP output tokens differ')
        require(len(native['tokens']) == row['output_tokens'], 'native output count differs')
        require(isinstance(native.get('draft_rows'), list) and bool(native['draft_rows']), 'native controller draft rows required')
        request_dir = self.runtime_evidence if number == 1 else self.runtime_evidence / f'req-{number:06d}'
        probe_path = request_dir / 'rank0/draft-depth-probe.jsonl'
        probe_bytes = probe_path.read_bytes()
        require(bool(probe_bytes) and probe_bytes.endswith(b'\n'), 'depth probe trace empty or incomplete')
        # Refuse concurrent request replacement rather than attaching mismatched artifacts.
        self.check_control()
        require(request_log.read_bytes() == log_bytes, 'request log advanced during capture')
        require(config_path.read_bytes() == config_bytes and native_path.read_bytes() == native_bytes,
                'native request/result changed during capture')
        require(probe_path.read_bytes() == probe_bytes, 'probe trace changed during capture')
        prompt = row['prompt_id']
        require(isinstance(prompt, str) and prompt not in ('', '.', '..') and Path(prompt).name == prompt,
                'unsafe prompt id')
        dest = self.destination / prompt
        (dest / 'rank0').mkdir(parents=True, exist_ok=False)
        (dest / 'rank0/native-result.json').write_bytes(native_bytes)
        (dest / 'rank0/draft-depth-probe.jsonl').write_bytes(probe_bytes)
        (dest / 'native-request.txt').write_bytes(config_bytes)
        save_json(dest / 'prompt-token-ids.json', row['prompt_token_ids'])
        save_json(dest / 'http-response.json', response)
        save_json(dest / 'capture.json', {'request': number, 'prompt_id': prompt,
            'control': self.control_identity, 'plan_sha256': sha(self.plan_bytes),
            'request_log_last_row': latest, 'request_log_sha256': sha(log_bytes),
            'native_result_source': str(native_path), 'native_result_sha256': sha(native_bytes),
            'native_request_sha256': sha(config_bytes), 'probe_source': str(probe_path),
            'probe_sha256': sha(probe_bytes), 'tokens_match_http': True,
            'prompt_tokens': np, 'output_tokens': len(native['tokens'])})
        self.last_request = number


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    args, suite_args = parser.parse_known_args()
    capture = Capture(args.evidence_dir)
    spec = importlib.util.spec_from_file_location('depth_probe_suite', SUITE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(on_result=capture, argv=suite_args)


if __name__ == '__main__':
    main()
