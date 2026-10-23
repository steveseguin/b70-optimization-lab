#!/usr/bin/env python3
"""Rendering-parity harness, step 2 (2026-10-23): messages -> the exact text the engine's token prefix came from.

Step 1 (render_parity.py) showed the pinned oracle tokenizer reproduces every sealed token list from the sealed
rendered text. This step covers the other half: the chat template. The template the runtime's model carries is
`tokenizer.chat_template` in GGUF shard 1's header (pinned header sha256 7c1460a9…); the copy in this directory,
`chat_template-7c1460a9.jinja`, was read out of that header on 2026-10-23 (shard fetched at the pinned revision,
whole-file and header sha256 both equal to the admission receipt's). The 12 sealed prompts were rendered with
that template by `baseline-llamacpp/prepare-prompts.py` (jinja2 ImmutableSandboxedEnvironment, one user message,
add_generation_prompt, thinking off), and the prompt manifest pins the template's sha256 (12827f24…).

This harness renders the suite's raw prompts the same way from the saved template and compares the bytes with the
sealed files, then renders the message shapes ctxkeeper sends (system + user, multi-turn, several system messages)
and records their hashes so an adapter can be checked against them later. Pass --gguf to read the template from a
shard-1 file instead of the saved copy; the header pin is checked first.

Usage: template_parity.py [--gguf shard1.gguf] [--out receipt.json]   (CPU only, read-only; needs jinja2)
"""
import argparse, hashlib, json, sys
from pathlib import Path

from jinja2.sandbox import ImmutableSandboxedEnvironment

LAB = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ORACLE = LAB / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'
SUITE = LAB / 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json'
SAVED = HERE / 'chat_template-7c1460a9.jinja'
PINNED_HEADER_SHA = '7c1460a95eb2e95377c32b14deb92cf74fe504d4feb5a62a40d48f78e9e0dcb8'
PINNED_HEADER_BYTES = 10946618
PINNED_TEMPLATE_SHA = '12827f24b742ea4e80cdc12dbcf9622227056b9f797252a3149263d4f9aaadce'

SHAPES = {
    'system+user': [{'role': 'system', 'content': 'You are a careful assistant.'},
                    {'role': 'user', 'content': 'What is 2+2?'}],
    'two-turn': [{'role': 'user', 'content': 'Name a colour.'},
                 {'role': 'assistant', 'content': 'Blue.'},
                 {'role': 'user', 'content': 'Another.'}],
    'two-systems': [{'role': 'system', 'content': 'Rule one.'},
                    {'role': 'system', 'content': 'Rule two.'},
                    {'role': 'user', 'content': 'Go.'}],
    'developer+user': [{'role': 'developer', 'content': 'Keep answers short.'},
                       {'role': 'user', 'content': 'Why is the sky blue?'}],
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def template_from_gguf(path: Path) -> tuple[str, dict]:
    from gguf import GGUFReader
    head = path.read_bytes()[:PINNED_HEADER_BYTES]
    r = GGUFReader(str(path))
    f = r.fields['tokenizer.chat_template']
    text = bytes(f.parts[f.data[0]]).decode('utf-8')
    return text, {'path': str(path), 'header_sha256': sha(head), 'header_matches_pin': sha(head) == PINNED_HEADER_SHA}


def render(env, template: str, messages, thinking=False) -> str:
    return env.from_string(template).render(messages=messages, add_generation_prompt=True, enable_thinking=thinking)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--gguf', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    if a.gguf:
        template, source = template_from_gguf(Path(a.gguf))
    else:
        template, source = SAVED.read_text(), {'path': str(SAVED), 'header_sha256': None, 'header_matches_pin': None}
    receipt = {'schema': 'own-runtime.template-parity.v1', 'template_source': source,
               'template_sha256': sha(template.encode()), 'pinned_template_sha256': PINNED_TEMPLATE_SHA,
               'template_matches_pin': sha(template.encode()) == PINNED_TEMPLATE_SHA,
               'manifest_template_sha256': json.loads((ORACLE / 'prompts/prompts.json').read_text())['template_sha256'],
               'render': {'add_generation_prompt': True, 'enable_thinking': False, 'environment': 'jinja2 ImmutableSandboxedEnvironment'},
               'prompts': [], 'shapes': {}, 'passed': False}
    env = ImmutableSandboxedEnvironment()
    suite = {p['id']: p['prompt'] for p in json.loads(SUITE.read_text())['prompts']}
    ok = 0
    for p in json.loads((ORACLE / 'prompts/prompts.json').read_text())['prompts']:
        sealed = (ORACLE / 'prompts' / Path(p['file']).name).read_bytes()
        rendered = render(env, template, [{'role': 'user', 'content': suite[p['id']]}]).encode()
        same = rendered == sealed
        ok += same
        receipt['prompts'].append({'id': p['id'], 'sealed_sha256': sha(sealed), 'manifest_rendered_sha256': p['rendered_sha256'],
                                   'rendered_sha256': sha(rendered), 'identical': same})
    for name, msgs in SHAPES.items():
        text = render(env, template, msgs)
        receipt['shapes'][name] = {'messages': msgs, 'rendered_sha256': sha(text.encode()), 'rendered': text}
    receipt['identical'] = f'{ok}/{len(receipt["prompts"])}'
    receipt['passed'] = (ok == len(receipt['prompts']) == 12 and receipt['template_matches_pin']
                         and receipt['manifest_template_sha256'] == PINNED_TEMPLATE_SHA
                         and source['header_matches_pin'] in (None, True))
    if a.out:
        Path(a.out).write_text(json.dumps(receipt, indent=2) + '\n')
    print(f"template sha256 matches pin: {receipt['template_matches_pin']}; header pin: {source['header_matches_pin']}; "
          f"sealed prompts rendered identically: {receipt['identical']}; passed: {receipt['passed']}")
    for name, s in receipt['shapes'].items():
        print(f'  shape {name}: {s["rendered_sha256"][:16]} {s["rendered"]!r}'[:200])
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
