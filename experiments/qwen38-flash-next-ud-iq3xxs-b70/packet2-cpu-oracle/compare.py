#!/usr/bin/env python3
"""Informational comparison with saved llama.cpp stdout; never a quality gate."""
import argparse
import json
from pathlib import Path
from oracle import Store, Tokenizer, HERE, sha, dump


def visible_stdout(source):
    raw = source.read_bytes()
    text = raw.decode()
    terminal = ' [end of text]'
    if terminal in text:
        text = text[:text.index(terminal)]
    else:
        assert text.endswith('\n\n'), 'unknown stdout framing'
        text = text[:-2]
    return raw, text


def text_comparison(left, right):
    count = 0
    for a, b in zip(left, right):
        if a != b: break
        count += 1
    return dict(agreement_characters=count,
        text_prefix_agrees=count == min(len(left), len(right)),
        first_text_divergence=(dict(index=count, left=left[count:count+80], right=right[count:count+80])
                               if count < min(len(left), len(right)) else None),
        left_characters=len(left), right_characters=len(right))


def compare(run, baseline, onecard=None):
    store = Store(); tok = Tokenizer(store.meta); store.close()
    records = {r['id']:r for r in json.loads((baseline/'runs.json').read_text()) if r['repeat']==1 and r.get('returncode')==0 and not r.get('failed',False)}
    results = []
    for f in sorted(run.glob('*/result.json')):
        oracle = json.loads(f.read_text())
        source = baseline/f"repeat1-{oracle['id']}.stdout"
        row = dict(id=oracle['id'],oracle_token_ids=oracle['tokens'],authority='CPU oracle; baseline informational only')
        if not oracle['tokens']:
            row.update(status='oracle-prefill-incomplete',oracle_status=oracle['status'])
            results.append(row); continue
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
    # Character prefixes are primary; retokenized IDs are supplemental only.
    for row in results:
        if row['status'] == 'compared':
            oracle = json.loads((run/row['id']/'result.json').read_text())
            _, text = visible_stdout(baseline/f"repeat1-{row['id']}.stdout")
            visible = [i for i in oracle['tokens'] if i not in (248044,248046)]
            oracle_text = tok.decode(visible)
            row.update(text_comparison(oracle_text, text))
            n = row['agreement_characters']
            stop_difference = None
            if n == len(text) < len(oracle_text) and row['baseline_end_of_text']:
                stop_difference = dict(index=n,oracle_text=oracle_text[n:n+80],baseline='end-of-text marker')
            elif n == len(oracle_text) < len(text) and row['oracle_end_of_text']:
                stop_difference = dict(index=n,oracle='end-of-text',baseline_text=text[n:n+80])
            row['first_termination_divergence'] = stop_difference
            row['completion_prefix_agrees'] = row['text_prefix_agrees'] and stop_difference is None
    onecard_rows = []
    baseline_pair = None
    if onecard is not None:
        raw, text = visible_stdout(onecard)
        source = baseline/'repeat1-incident-retrospective.stdout'
        raw2, text2 = visible_stdout(source)
        baseline_pair = dict(left=str(onecard),right=str(source),left_sha256=sha(raw),
                             right_sha256=sha(raw2),**text_comparison(text,text2))
        f = run/'incident-retrospective/result.json'
        if f.exists() and json.loads(f.read_text())['tokens']:
            oracle = json.loads(f.read_text())
            visible = [i for i in oracle['tokens'] if i not in (248044,248046)]
            onecard_rows.append(dict(id=oracle['id'],source=str(onecard),sha256=sha(raw),
                **text_comparison(tok.decode(visible),text)))
    dump(run/'baseline-comparison.json',dict(informational_only=True,baseline=str(baseline),
        baseline_completed_rows=len(records),rows=results,onecard_rows=onecard_rows,
        baseline_vs_baseline=baseline_pair,
        missing_oracle_ids=sorted(set(records)-{r['id'] for r in results if r['oracle_token_ids']}),
        comparator_sha256=sha(Path(__file__).read_bytes()),
        oracle_receipt_sha256=sha((run/'receipt.json').read_bytes()),
        incomplete_prefill_ids=[r['id'] for r in results if r['status']=='oracle-prefill-incomplete'],
        caveat='Neither llama.cpp topology is arithmetic authority; their outputs already differ.'))
    return results


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run',type=Path)
    ap.add_argument('--baseline',type=Path,default=HERE.parent/'baseline-llamacpp/runs/window-20261011-boot13858eef')
    ap.add_argument('--onecard',type=Path,default=HERE.parent/'explore/onecard-fit-20261011b/stdout.txt')
    args = ap.parse_args()
    print(json.dumps(compare(args.run,args.baseline,args.onecard),indent=2))
