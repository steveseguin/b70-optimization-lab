#!/usr/bin/env python3
"""CPU-only: render the frozen publisher template and emit the 24-run plan."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from jinja2.sandbox import ImmutableSandboxedEnvironment

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SUITE = REPO / 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json'
HEADER = REPO / 'experiments/own-xpu-runtime/stage2/packet1c/headers/UD-IQ3_XXS__Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf.header.gz'
PARSER = REPO / 'experiments/own-xpu-runtime/stage1/packet1b/loaders/headers.py'
BUILD = Path('/home/steve/build/flash-next-iq3-baseline-20261010/build')
MODEL = '/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('headers', PARSER)
    headers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(headers)
    raw = gzip.decompress(HEADER.read_bytes())
    meta = headers.gguf_header(io.BytesIO(raw), 10946624)['metadata']
    assert meta['general.architecture'] == 'qwen4exp'
    template = meta['tokenizer.chat_template']
    renderer = ImmutableSandboxedEnvironment().from_string(template)
    suite = json.loads(SUITE.read_text())
    assert len(suite['prompts']) == 12
    rows = []
    for p in suite['prompts']:
        rendered = renderer.render(messages=[{'role': 'user', 'content': p['prompt']}],
                                   add_generation_prompt=True, enable_thinking=False)
        # This is a verification of the saved template's simple one-user case.
        assert rendered == '<|im_start|>user\n' + p['prompt'] + '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
        prompt = output / (p['id'] + '.txt')
        prompt.write_bytes(rendered.encode())
        rows.append({'id': p['id'], 'raw_sha256': sha(p['prompt'].encode()),
                     'rendered_sha256': sha(rendered.encode()), 'file': str(prompt.resolve())})
    manifest = {'suite_path': str(SUITE.relative_to(REPO)), 'suite_sha256': sha(SUITE.read_bytes()),
                'header_path': str(HEADER.relative_to(REPO)), 'header_sha256': sha(HEADER.read_bytes()),
                'parser_sha256': sha(PARSER.read_bytes()), 'template_sha256': sha(template.encode()),
                'architecture': meta['general.architecture'], 'thinking': False, 'system_message': None,
                'prompts': rows}
    (output / 'prompts.json').write_text(json.dumps(manifest, indent=2) + '\n')
    commands = []
    for repeat in (1, 2):
        for row in rows:
            commands.append({'repeat': repeat, 'id': row['id'], 'argv': [
                str(BUILD / 'bin/llama-completion'), '--model', MODEL,
                '--device', 'SYCL0,SYCL1', '--split-mode', 'layer', '--tensor-split', '1,1',
                '--gpu-layers', 'all', '--fit', 'off',
                '--override-tensor', '^token_embd\\.weight$=CPU,^per_layer_token_embd\\.weight$=CPU',
                '--ctx-size', '4096', '--batch-size', '512', '--ubatch-size', '128',
                '--cache-type-k', 'f16', '--cache-type-v', 'f16', '--flash-attn', 'off',
                '--threads', '2', '--threads-batch', '2', '--parallel', '1',
                '--temp', '0', '--seed', '20260609', '--top-k', '1', '--top-p', '1',
                '--min-p', '0', '--repeat-penalty', '1', '--predict', '64',
                '--no-conversation', '--no-display-prompt', '--simple-io', '--color', 'off',
                '--log-colors', 'off', '--no-warmup', '--no-context-shift', '--perf',
                '--file', row['file']]})
    (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(prepare(a.out), indent=2))
