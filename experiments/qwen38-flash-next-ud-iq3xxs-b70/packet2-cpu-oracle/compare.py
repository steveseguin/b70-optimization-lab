#!/usr/bin/env python3
"""Informational comparison with saved llama.cpp stdout; never a quality gate."""
import argparse
import json
from pathlib import Path
from oracle import Store, Tokenizer, HERE, sha, dump


def compare(run, baseline):
    store = Store(); tok = Tokenizer(store.meta); store.close()
    records = {r['id']:r for r in json.loads((baseline/'runs.json').read_text()) if r['repeat']==1}
    results = []
    for f in sorted(run.glob('*/result.json')):
        oracle = json.loads(f.read_text())
        source = baseline/f"repeat1-{oracle['id']}.stdout"
        row = dict(id=oracle['id'],oracle_token_ids=oracle['tokens'],authority='CPU oracle; baseline informational only')
        if not source.exists() or oracle['id'] not in records:
            row['status'] = 'baseline-row-not-complete'; results.append(row); continue
        raw = source.read_bytes(); text = raw.decode()
        terminal = ' [end of text]'
        eos = terminal in text
        if eos: text = text[:text.index(terminal)]
        else:
            # llama-completion appends two newlines on its normal exit.
            # Preserve any model-produced whitespace before those bytes.
            assert text.endswith('\n\n'), 'unknown stdout framing'
            text = text[:-2]
        baseline_ids = tok.encode(text)
        visible = [i for i in oracle['tokens'] if i not in (248044,248046)]
        agree = 0
        for a,b in zip(visible,baseline_ids):
            if a != b: break
            agree += 1
        oracle_text = tok.decode(visible)
        chars = 0
        for a,b in zip(oracle_text,text):
            if a != b: break
            chars += 1
        row.update(status='compared',baseline_stdout_sha256=sha(raw),baseline_record=records[oracle['id']],
            baseline_retokenized_ids=baseline_ids,agreement_tokens=agree,agreement_characters=chars,
            oracle_visible_tokens=len(visible),baseline_visible_tokens=len(baseline_ids),
            baseline_end_of_text=eos,oracle_end_of_text=oracle['status']=='eos',
            stdout_terminal_token_identity_available=False,
            first_divergence=(dict(index=agree,oracle_id=visible[agree],baseline_id=baseline_ids[agree])
                if agree < min(len(visible),len(baseline_ids)) else None),
            text_prefix_agrees=oracle_text.startswith(text) or text.startswith(oracle_text),
            caveat='Retokenized text can merge tokens at the truncation boundary; EOS ID is not recoverable from stdout.')
        results.append(row)
    dump(run/'baseline-comparison.json',dict(informational_only=True,baseline=str(baseline),rows=results))
    return results


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run',type=Path)
    ap.add_argument('--baseline',type=Path,default=HERE.parent/'baseline-llamacpp/runs/window-20261011-boot13858eef')
    args = ap.parse_args()
    print(json.dumps(compare(args.run,args.baseline),indent=2))
