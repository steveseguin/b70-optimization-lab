#!/usr/bin/env python3
"""C68: remove only the current upstream memory-contract suffix from C67.

The history and NOTES were generated with the candidate contract. This is a
conditional current-prompt ablation, not an end-to-end original baseline.
Production memory accounting and the frozen C67 interpreter remain unchanged.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

import main_history_authority_probe as prior

sha, dump, load = prior.sha, prior.dump, prior.load
SOURCE_FIXTURE = prior.BASE / 'campaign67-authority-fixture'
CONTRACT = prior.old.CONTRACT
ARMS = prior.ARMS
SCOPE = ('Synthetic current-prompt ablation conditional on candidate-generated history and NOTES; '
         'no original-baseline end-to-end claim, real task action, or quality promotion.')


def remove_suffix(request):
    """Remove one exact trailing system suffix, and prove the inverse immediately."""
    messages = request.get('messages') or []
    if not messages or messages[0].get('role') != 'system':
        raise ValueError('expected original leading system message')
    text = messages[0].get('content')
    if not isinstance(text, str) or not text.endswith(CONTRACT) or text.count(CONTRACT) != 1:
        raise ValueError('expected exactly one trailing registered contract')
    stripped = copy.deepcopy(request)
    stripped['messages'][0]['content'] = text[:-len(CONTRACT)]
    restored = copy.deepcopy(stripped)
    restored['messages'][0]['content'] += CONTRACT
    if restored != request:
        raise RuntimeError('suffix inverse failed')
    return stripped


def run_arm(folder, arm, ask, expected_first=None):
    source = folder / 'c67'
    original_capture = load(source / 'cpu-capture.json')[arm]
    pairs = []
    def stripped_ask(request):
        actual = remove_suffix(request)
        pairs.append({'keeper_request': copy.deepcopy(request), 'request': copy.deepcopy(actual)})
        if len(pairs) == 1 and expected_first is not None and actual != expected_first:
            raise RuntimeError('first wire request differs from frozen no-suffix capture')
        return ask(actual)
    def rewrite_calls(calls):
        if len(calls) != len(pairs):
            # A prior C67 boundary failure can occur before the wrapper is called.
            return [{'keeper_request': row['request'], 'request': pairs[i]['request'] if i < len(pairs) else None,
                     'response': row['response']} for i, row in enumerate(calls)]
        return [dict(row, keeper_request=pair['keeper_request'], request=pair['request'])
                for row, pair in zip(calls, pairs)]
    try:
        row = prior.run_arm(source, arm, stripped_ask, original_capture)
    except BaseException as exc:
        evidence = getattr(exc, 'probe_evidence', {})
        if 'calls' in evidence:
            evidence['calls'] = rewrite_calls(evidence['calls'])
        exc.probe_evidence = evidence
        raise
    row['calls'] = rewrite_calls(row['calls'])
    row['current_contract_removed'] = True
    row['inverse_suffix_check_every_call'] = True
    return row


def captures(folder):
    original = prior.captures(folder / 'c67')
    frozen = load(folder / 'c67/cpu-capture.json')
    if original != frozen:
        raise RuntimeError('original C67 capture no longer reproduces')
    rows = {arm: run_arm(folder, arm, lambda _: prior.old.fake_response()) for arm in ARMS}
    output = {}
    for arm, row in rows.items():
        if len(row['calls']) != 1 or row['call_kinds'] != ['main'] or row['recalls_served']:
            raise RuntimeError('CPU capture changed production path')
        call = row['calls'][0]
        expected = remove_suffix(frozen[arm])
        if call['request'] != expected or call['keeper_request'] != frozen[arm]:
            raise RuntimeError('no-suffix capture changed more than the registered suffix')
        output[arm] = call['request']
    if [len(output[arm]['messages']) for arm in ARMS] != [12, 14, 12]:
        raise RuntimeError('registered message counts changed')
    return output


def prepare(folder):
    if folder.exists():
        raise ValueError('refusing existing fixture')
    prior.verify_fixture(SOURCE_FIXTURE)
    folder.mkdir(parents=True)
    shutil.copytree(SOURCE_FIXTURE, folder / 'c67')
    # The copied original manifest and every original file remain byte-identical.
    original_files = {str(p.relative_to(SOURCE_FIXTURE)): sha(p) for p in SOURCE_FIXTURE.rglob('*') if p.is_file()}
    copied_files = {str(p.relative_to(folder / 'c67')): sha(p) for p in (folder / 'c67').rglob('*') if p.is_file()}
    if original_files != copied_files:
        raise RuntimeError('C67 fixture copy differs')
    dump(folder / 'cpu-capture.json', captures(folder))
    sources = [Path(__file__), Path(prior.__file__), Path(prior.old.__file__), SOURCE_FIXTURE / 'manifest.json',
               Path(prior.ck.__file__), prior.old.LAB / 'tools/ctxkeeper/notesdelta.py']
    manifest = {'schema': 'ctxkeeper.main-history-authority-baseline-fixture.v1', 'scope': SCOPE,
        'source_fixture': str(SOURCE_FIXTURE), 'contract_removed': CONTRACT,
        'source_pins': {str(p): sha(p) for p in sources},
        'pins': {str(p.relative_to(folder)): sha(p) for p in folder.rglob('*') if p.is_file()},
        'control_gate': {'messages': 12, 'single_terminal_call': True, 'no_external_actions': True,
                         'no_recalls': True, 'prompt_tokens': 'record only; 8627 is not required'},
        'transformation': 'remove only exact trailing system CONTRACT at current upstream callback; preserve production memory accounting',
        'configuration': {'arms': list(ARMS), 'rounds': 1, 'max_upstream_calls_per_arm': prior.MAX_CALLS,
                          'max_external_actions_per_arm': prior.MAX_ACTIONS, 'tool_parser': 'unchanged C67'}}
    dump(folder / 'manifest.json', manifest)
    print('Prepared separate C68 fixture; original C67 subtree is byte-identical.', flush=True)


def verify_fixture(folder):
    manifest = load(folder / 'manifest.json')
    if manifest['scope'] != SCOPE or manifest['contract_removed'] != CONTRACT:
        raise ValueError('scope or removed contract changed')
    for name, expected in manifest['source_pins'].items():
        if sha(Path(name)) != expected:
            raise ValueError('original source changed: ' + name)
    for name, expected in manifest['pins'].items():
        if sha(folder / name) != expected:
            raise ValueError('frozen C68 file changed: ' + name)
    prior.verify_fixture(Path(manifest['source_fixture']))
    prior.verify_fixture(folder / 'c67')
    return manifest


def cpu_check(folder, output):
    if output.exists():
        raise ValueError('refusing existing result')
    verify_fixture(folder)
    actual = captures(folder)
    if actual != load(folder / 'cpu-capture.json'):
        raise RuntimeError('frozen baseline captures changed')
    dump(output, {'complete': True, 'cpu_check': True, 'promotion': False, 'scope': SCOPE,
        'fixture_manifest_sha256': sha(folder / 'manifest.json'),
        'checks': {'all_source_pins': True, 'original_c67_subtree_preserved': True,
                   'all_three_inverse_suffix_proofs': True, 'unchanged_parser_and_keeper': True,
                   'no_notes_regeneration_cut_or_restart': True, 'message_counts': [12, 14, 12]}})


def control_matches(row):
    # Deliberately different from C67: the shorter prompt cannot have 8627 tokens.
    first = row['calls'][0] if row.get('calls') else {}
    return (row.get('outcome') == 'terminal' and len(row.get('calls', [])) == 1
            and not row.get('actions') and row.get('recalls_requested') == row.get('recalls_served') == 0
            and len((first.get('request') or {}).get('messages', [])) == 12)


def run(args):
    if args.json.exists():
        raise ValueError('refusing existing result')
    manifest = verify_fixture(args.fixture)
    frozen = load(args.fixture / 'cpu-capture.json')
    result = {'schema': 'ctxkeeper.main-history-authority-baseline-probe.v1', 'complete': False,
        'cpu_check': False, 'promotion': False, 'scope': SCOPE, 'semantic_pass': None,
        'fixture_manifest_sha256': sha(args.fixture / 'manifest.json'), 'script_sha256': sha(Path(__file__)),
        'control_gate': manifest['control_gate'], 'arms': []}
    dump(args.json, result)
    def ask(request):
        wire = urllib.request.Request(args.base_url.rstrip('/') + '/chat/completions',
            data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(wire, timeout=600) as stream:
            return json.load(stream)
    for arm in ARMS:
        started = time.monotonic()
        try:
            row = run_arm(args.fixture, arm, ask, frozen[arm])
        except BaseException as exc:
            result.update(error=f'{type(exc).__name__}: {exc}', failed_arm=arm,
                          failed_arm_evidence=getattr(exc, 'probe_evidence', {}))
            dump(args.json, result)
            raise
        row['seconds'] = round(time.monotonic() - started, 3)
        result['arms'].append(row)
        if arm == 'control':
            result['control_matched'] = control_matches(row)
            result['control_prompt_tokens_recorded_only'] = row['calls'][0]['response'].get('usage', {}).get('prompt_tokens')
            if not result['control_matched']:
                result.update(complete=True, branches_skipped=True, decision='inconclusive: no-suffix control terminal gate failed')
                dump(args.json, result)
                return
        else:
            deleted = any(a.get('action') == 'delete' for a in row['actions'])
            row['structural_screen_pass'] = (row['outcome'] == 'terminal' and
                ((deleted and not row['artifact']['exists']) if arm == 'genuine' else (not deleted and row['artifact']['exists'])))
        dump(args.json, result)
        print(f"{arm}: {row['outcome']}; simulated actions={len(row['actions'])}; recalls={row['recalls_served']}", flush=True)
    result.update(complete=True, decision='manual comparison with C67 required; conditional current-prompt ablation only')
    dump(args.json, result)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare', type=Path)
    ap.add_argument('--fixture', type=Path)
    ap.add_argument('--cpu-check', action='store_true')
    ap.add_argument('--base-url')
    ap.add_argument('--rounds', type=int, default=1)
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    if args.rounds != 1:
        ap.error('only one registered round is allowed')
    if args.prepare:
        prepare(args.prepare)
    elif args.cpu_check and args.fixture and args.json:
        cpu_check(args.fixture, args.json)
    elif args.fixture and args.base_url and args.json:
        run(args)
    else:
        ap.error('use --prepare DIR, --cpu-check --fixture DIR --json FILE, or --fixture DIR --base-url URL --json FILE')


if __name__ == '__main__':
    main()
