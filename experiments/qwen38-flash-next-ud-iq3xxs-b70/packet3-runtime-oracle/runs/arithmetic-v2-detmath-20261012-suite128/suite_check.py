#!/usr/bin/env python3
"""Read-only, standard-library exact suite comparison. Never loads model/device code."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
MANIFEST = ROOT / 'experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json'
PROMPT_IDS = ('incident-retrospective', 'code-review', 'customer-email', 'sql-debugging',
              'release-plan', 'benchmark-analysis', 'architecture-tradeoff',
              'bug-report-synthesis', 'technical-guide', 'risk-register',
              'performance-hypotheses', 'decision-memo')
IDENTITY = 'iq3-p17-detmath-v2'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path):
    return json.loads(path.read_text())

def require(condition, message):
    if not condition:
        raise ValueError(message)

def token_record(directory):
    # Runtime writes receipt.json; CPU oracle writes result.json plus orchestration receipt.
    receipt_path = directory/'receipt.json'
    receipt = read(receipt_path) if receipt_path.exists() else {}
    require(receipt.get('passed') is not False and not receipt.get('teardown_pending'), 'runtime receipt failed')
    if receipt.get('schema') == 'own-runtime.iq3.packet26.run.v1':
        require(receipt.get('passed') is True, 'runtime receipt failed')
        record = receipt
    else:
        record = read(directory/'result.json')
        require(record.get('schema') == 'iq3-runtime-cpu-oracle.v1', 'unknown output schema')
        require(record.get('status') in ('token-cap','eos') and not record.get('error'), 'incomplete oracle result')
    require(record.get('arithmetic') == IDENTITY, 'wrong arithmetic identity')
    tokens = record.get('tokens')
    require(isinstance(tokens,list) and all(type(t) is int for t in tokens), 'malformed tokens')
    if record.get('schema') == 'iq3-runtime-cpu-oracle.v1':
        require(bool(tokens) and ((record['status']=='eos') == (tokens[-1] in (248044,248046))), 'EOS status mismatch')
        require(record['status']=='eos' or len(tokens)==128, 'non-EOS oracle truncated')
    return tokens

def fixture_inventory(directory, count):
    indices=[i for i in range(1,count+1) if i<=8 or 97<=i<=104]
    steps = {f'step{i}' for i in indices}
    require({p.name for p in directory.glob('step*') if p.is_dir()} == steps, 'fixture step coverage differs')
    inventory = {}
    for i in indices:
        step = directory/f'step{i}'
        records = [json.loads(line) for line in (step/'layers.jsonl').read_text().splitlines()]
        require([r.get('layer') for r in records] == list(range(48)), f'step{i} layer indices')
        require({p.name for p in step.glob('*.bf16')} == {f'layer-{j:02}.bf16' for j in range(48)}, f'step{i} fixture filenames')
        for row in records:
            name = f"step{i}/layer-{row['layer']:02}.bf16"
            path = directory/name
            require(row.get('shape') == [1,4,2560] and row.get('dtype') == 'BF16 little-endian', f'{name} shape/dtype')
            require(path.stat().st_size == 20480, f'{name} length')
            require(sha(path) == row.get('sha256'), f'{name} recorded hash differs')
            inventory[name] = row['sha256']
    return inventory

def check_prompt(actual, oracle, entry=None, repo_root=ROOT):
    if (actual/'run').is_dir():
        if (actual/'receipt.json').exists():
            wrapper = read(actual/'receipt.json')
            require(wrapper.get('passed') is not False and not wrapper.get('teardown_pending'), 'runtime wrapper failed')
        actual = actual/'run'
    if entry is not None:
        require(sha(oracle/'receipt.json') == entry['oracle_receipt_sha256'], 'oracle receipt binding differs')
        bundle = repo_root/entry['input_bundle']
        require(set(entry['input_bundle_hashes']) == {'tokens.txt','input.json','identity.tsv','plan.tsv','vocab.bin'}, 'bundle file coverage')
        for name,digest in entry['input_bundle_hashes'].items():
            require(Path(name).name == name and sha(bundle/name) == digest, 'input bundle binding differs')
        inp = read(bundle/'input.json')
        require(inp['tokens'] == read(oracle/'input.json')['tokens'] == list(map(int,(bundle/'tokens.txt').read_text().split())), 'input token equality')
        require(len(inp['tokens']) == entry['prompt_tokens'], 'input token count')
        receipt = read(oracle/'receipt.json')
        require(sha(bundle/'input.json') == sha(oracle/'input.json') == receipt['input_sha256'], 'oracle input binding differs')
        require(sha(oracle/'validation.json') == receipt['validation_sha256'], 'oracle fixture binding differs')
        require(receipt.get('verified') is True and sha(oracle/'result.json') == receipt['result_sha256'], 'oracle result binding differs')
    expected = token_record(oracle)
    require(1 <= len(expected) <= 128, 'oracle token count')
    require(len(expected)==128 or expected[-1] in (248044,248046), 'oracle truncated before EOG')
    require(not any(t in (248044,248046) for t in expected[:-1]), 'oracle continued after EOG')
    if entry is not None:
        require(entry['generated_tokens']==len(expected) and entry['ended_early']==(len(expected)<128), 'manifest generation count')
    observed = token_record(actual)
    require(observed==expected, 'tokens differ: first index (one-based) '+str(next((i+1 for i in range(max(len(observed),len(expected))) if i>=len(observed) or i>=len(expected) or observed[i]!=expected[i]),None)))
    reference = fixture_inventory(oracle,len(expected))
    if entry is not None:
        require(reference == read(oracle/'validation.json')['fixture_hashes'], 'oracle fixture inventory binding differs')
    candidate = fixture_inventory(actual,len(expected))
    for name,digest in reference.items():
        require(candidate[name]==digest and (actual/name).read_bytes()==(oracle/name).read_bytes(), name+' byte mismatch')
    return len(expected),len(reference)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('outputs',type=Path,help='Directory containing one subdirectory per prompt (optionally prompt/run/)')
    ap.add_argument('--oracle-root',type=Path,default=HERE)
    ap.add_argument('--manifest',type=Path,default=MANIFEST)
    a=ap.parse_args(argv)
    manifest=read(a.manifest)
    require(manifest.get('arithmetic')==IDENTITY and manifest.get('context')==256 and manifest.get('token_cap')==128,'manifest identity')
    entries={r['prompt_id']:r for r in manifest['prompts']}
    require(len(entries)==len(manifest['prompts']) and not set(entries)-set(PROMPT_IDS),'duplicate/unknown prompt')
    passed=token_total=fixture_total=0
    for prompt in PROMPT_IDS:
        try:
            require(prompt in entries,'oracle not yet completed')
            tokens,fixtures=check_prompt(a.outputs/prompt,a.oracle_root/prompt,entries[prompt])
            passed+=1;token_total+=tokens;fixture_total+=fixtures
            print(f'{prompt}: PASS tokens={tokens} fixtures={fixtures}')
        except (OSError,ValueError,KeyError,TypeError) as error:
            print(f'{prompt}: FAIL {error}')
    print(f'TOTAL prompts={passed}/12 tokens={token_total} fixtures={fixture_total} exact={passed==12}')
    return 0 if passed==12 and manifest.get('complete') is True else 1

if __name__=='__main__':
    try:
        sys.exit(main())
    except (OSError,ValueError,KeyError,TypeError) as error:
        print('FAIL '+str(error),file=sys.stderr)
        sys.exit(1)
