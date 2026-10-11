"""Read-only evidence snapshot: distinguish prompt inputs from generated tokens."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
P13 = HERE.parent
ROOT = P13.parents[3]
ORACLE = ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'


def classify(tokens, timings, generated):
    rows = [r for r in timings if r.get('kind') == 'token']
    prefill = [r for r in rows if r['token_index'] < len(tokens)]
    return dict(completed_prompt_positions=len(prefill), prompt_positions=len(tokens),
                observed_prefill_matches_prompt=all(r['input_token'] == tokens[r['token_index']] for r in prefill),
                prefill_complete=len(prefill) == len(tokens),
                generation_established=bool(generated), generated_tokens=generated,
                observed_input_tokens=[r['input_token'] for r in rows])


def snapshot(output):
    sys.path.insert(0, str(ORACLE))
    sys.path.insert(0, str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
    from tokenizer import Tokenizer
    from loaders.headers import gguf_header
    inp = P13/'build/input'
    window = P13/'build/card3-first-token-a'
    run = window/'run'
    oracle = ORACLE/'runs/official-sigmoid-20261011/incident-retrospective'
    inputs = json.loads((inp/'input.json').read_text())
    oracle_input = json.loads((oracle/'input.json').read_text())
    tokens = list(map(int, (inp/'tokens.txt').read_text().split()))
    shard = Path(inputs['model_dir'])/(inp/'identity.tsv').read_text().splitlines()[0].split()[0]
    with shard.open('rb') as f:
        meta = gguf_header(f, shard.stat().st_size)['metadata']
    tok = Tokenizer(meta)
    # A live append can end in a partial JSON line; use only complete rows.
    raw_timing = (run/'timings.jsonl').read_bytes()
    timing = [json.loads(line) for line in raw_timing.splitlines(keepends=True) if line.endswith(b'\n')]
    stdout = (window/'stdout.txt').read_text()
    generated = [int(line.split()[1]) for line in stdout.splitlines(keepends=True)
                 if line.endswith('\n') and line.startswith('token_id ')]
    receipt = json.loads((run/'receipt.json').read_text()) if (run/'receipt.json').exists() else None
    if receipt is not None:
        generated = receipt['tokens']
    oracle_result = json.loads((oracle/'result.json').read_text())
    fixtures = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((run/'step1').glob('layer-*.bf16'))}
    result = dict(schema='iq3-first-token-input-audit.v1', observed_utc=datetime.now(timezone.utc).isoformat(),
        runtime_window=str(window.relative_to(ROOT)), **classify(tokens, timing, generated),
        runtime_input_matches_oracle=tokens == oracle_input['tokens'] == inputs['tokens'],
        rendered_prompt=tok.decode(tokens), runtime_input_tokens=tokens,
        alleged_generated_tokens=[846,198,2523,513,60566,449,13343,2015],
        alleged_generated_text=tok.decode([846,198,2523,513,60566,449,13343,2015]),
        runtime_generated_text=tok.decode(generated) if generated else None,
        oracle_generated_tokens=oracle_result['tokens'], oracle_generated_text=tok.decode(oracle_result['tokens']),
        oracle_nine_token_text=tok.decode(oracle_result['tokens'][:9]),
        oracle_step0=oracle_result['steps'][0], device_step1_hashes=fixtures,
        timing_snapshot_sha256=hashlib.sha256(raw_timing).hexdigest(),
        timing_snapshot_bytes=len(raw_timing),
        stdout_bytes=len(stdout.encode()), runtime_receipt_present=receipt is not None,
        input_sha256=hashlib.sha256((inp/'tokens.txt').read_bytes()).hexdigest(),
        prompt_text_matches_oracle_file=tok.decode(tokens)==(ORACLE/'prompts/incident-retrospective.txt').read_text(),
        token_timing_rows=[r for r in timing if r.get('kind')=='token'])
    Path(output).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['runtime_input_tokens','token_timing_rows','oracle_generated_tokens']}, indent=2))


if __name__ == '__main__':
    snapshot(sys.argv[1])
