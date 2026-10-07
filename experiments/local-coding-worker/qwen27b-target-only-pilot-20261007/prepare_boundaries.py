#!/usr/bin/env python3
"""Freeze prompt lengths using local pinned tokenizer files; no model or network."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokenizer-dir', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(USE_TORCH='0', USE_TF='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      TOKENIZERS_PARALLELISM='false')
    import transformers
    import tokenizers
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(args.tokenizer_dir),
                    local_files_only=True, trust_remote_code=False)
    def count(messages):
        value = tokenizer.apply_chat_template(messages, tokenize=True,
                       add_generation_prompt=True, enable_thinking=False)
        return len(value['input_ids']) if hasattr(value, 'keys') else len(value)
    def messages(padding):
        return [{'role': 'system', 'content': 'Answer only the final request. The padding is irrelevant. Return the requested marker without explanation.'},
                {'role': 'user', 'content': '[BEGIN PADDING]\n' + ' pad' * padding +
                 '\n[END PADDING]\nFinal request: reply exactly LAB42.'}]
    cases = {}
    base = count(messages(0))
    for target in (511, 512, 513, 1025):
        candidates = [n for n in range(max(0, target - base - 8), target - base + 9)
                      if count(messages(n)) == target]
        if not candidates:
            raise ValueError('Cannot construct exact boundary length with the fixed padding')
        padding = candidates[0]
        prompt = messages(padding)
        if count(prompt) != target:
            raise ValueError('Tokenizer does not preserve the preregistered padding construction')
        cases[str(target)] = {'input_tokens': target, 'padding_repetitions': padding,
                             'messages': prompt, 'expected_text': 'LAB42'}
    worker_path = HERE.parents[2] / 'worker/run.py'
    tree = ast.parse(worker_path.read_text())
    system = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'SYSTEM' for t in node.targets))
    system_count = count([{'role': 'system', 'content': system}, {'role': 'user', 'content': 'Smoke check.'}])
    if system_count <= 300:
        raise ValueError('Unexpectedly short worker system prompt')
    protocol = {'schema': 'lab.qwen27b.boundary-protocol.v1', 'status': 'preregistered-unrun',
                'purpose': 'Finite marker and repeat checks around 512-token prefill boundaries; not a full arithmetic oracle',
                'model_revision': '017b9c7af6b5689d5dd426a76e0bc077eb5ca20a',
                'profile_sha256': hashlib.sha256((HERE / 'worker-profile.json').read_bytes()).hexdigest(),
                'transformers': transformers.__version__, 'tokenizers': tokenizers.__version__,
                'tokenizer_files': {name: hashlib.sha256((args.tokenizer_dir / name).read_bytes()).hexdigest()
                                    for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja')},
                'worker_system_sha256': hashlib.sha256(system.encode()).hexdigest(),
                'worker_system_smoke_input_tokens': system_count,
                'generation': {'temperature': 0, 'top_p': 1, 'seed': 42, 'enable_thinking': False},
                'max_output_tokens': 16, 'network_wall_time_limit_s': 300,
                'retries': 0, 'known_one_token_prompt_bug_repaired': False,
                'minimum_total_prompt_tokens_exclusive': 1,
                'cases': cases, 'order': ['511', '513', '512', '1025'] * 2}
    with (HERE / 'boundary-protocol.json').open('x') as stream:
        json.dump(protocol, stream, indent=2); stream.write('\n')
    print(json.dumps({'lengths': list(cases), 'worker_system_smoke_input_tokens': system_count}))


if __name__ == '__main__':
    main()
