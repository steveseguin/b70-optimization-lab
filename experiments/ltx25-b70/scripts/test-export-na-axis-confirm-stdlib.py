#!/usr/bin/env python3
"""Offline confirmation-export checks; no terminal export or live campaign read."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('na_axis_confirmation_export_test', LANE / 'scripts/export-na-axis-confirm.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    checks = []
    def check(name, condition):
        module.require(condition, name)
        checks.append(name)
    def rejects(name, action, expected):
        try:
            action()
        except RuntimeError as error:
            check(name, expected in str(error))
            return
        raise AssertionError('Expected refusal: ' + name)

    old_source = (LANE / 'scripts/export-na-axis-screen.py').read_bytes()
    check('original-screen-exporter-unchanged', module.digest(old_source) == module.HELPERS['export-na-axis-screen.py'])
    old_tree, new_tree = ast.parse(old_source), ast.parse(Path(module.__file__).read_text())
    for name in ('require', 'identity', 'safe', 'read_stable', 'digest', 'unique_json', 'add_tree',
                 'archive_name', 'parsed_optional', 'timing_values'):
        old = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        new = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        check('reviewed-helper-unchanged-' + name, ast.dump(old) == ast.dump(new))

    client_raw = (LANE / 'scripts/run-na-axis-confirm.py').read_bytes()
    check('confirmation-client-final-pin-current', module.digest(client_raw) == module.CLIENT_SHA)
    check('admission-helper-final-pin-current',
        module.digest((LANE / 'scripts/ltx_na_axis_confirmation.py').read_bytes()) == module.ADMISSION_SHA)
    tree = ast.parse(client_raw)
    schedule_function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'schedule')
    blocks_assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and
                             any(isinstance(t, ast.Name) and t.id == 'BLOCKS' for t in n.targets))
    blocks = ast.literal_eval(blocks_assignment.value)
    namespace = {'require': module.require, 're': module.re, 'BLOCKS': blocks}
    exec(compile(ast.Module(body=[schedule_function], type_ignores=[]), '<pure-confirmation-schedule>', 'exec'), namespace)
    schedule = module.expected_schedule(module.CAMPAIGN)
    check('confirmation18-schedule-matches-client', len(schedule) == 18 and schedule == namespace['schedule'](module.CAMPAIGN))
    check('every-fixture-has-both-orders', all({r['order'] for r in schedule if r['fixture'] == fixture} == {'OCO', 'COC'}
                                             for fixture in ('boat', 'marble', 'bird')))
    prereg = {'campaign': module.CAMPAIGN, 'packet_manifest_sha256': module.PACKET_SHA,
        'client_sha256': module.CLIENT_SHA, 'validator_sha256': module.VALIDATOR_SHA,
        'admission_helper_sha256': module.ADMISSION_SHA, 'prior_client_sha256': module.PRIOR_CLIENT_SHA,
        'inherited_v3_sha256': module.HELPERS['run-multiblock-screen-v3.py'],
        'max_requests': 18, 'schedule': schedule, 'frozen_helpers': {name: module.HELPERS[name]
            for name in ('profile-clip.py', 'compare-clip.py', 'run-stability.py')}}
    rows = [dict(row, status='passed') for row in schedule]
    progress = {'status': 'passed', 'completed_requests': 18, 'rows': rows}
    check('complete18-terminal-pass-accepted', len(module.terminal_rows(progress, prereg, module.CAMPAIGN)[1]) == 18)
    check('partial-terminal-failure-accepted', module.terminal_rows({'status': 'failed', 'rows': rows[:4]}, prereg, module.CAMPAIGN)[1] == rows[:4])
    rejects('old11-request-passed-shape-refused', lambda: module.terminal_rows(dict(progress, rows=rows[:11], completed_requests=11), prereg, module.CAMPAIGN), 'Incomplete passed')
    rejects('ongoing-confirmation-refused', lambda: module.terminal_rows(dict(progress, status='running'), prereg, module.CAMPAIGN), 'not terminal')
    changed = copy.deepcopy(prereg); changed['schedule'][3]['order'] = 'OCO'
    rejects('changed-confirmation-order-refused', lambda: module.terminal_rows(progress, changed, module.CAMPAIGN), 'Invalid bounded')
    rejects('old-client-identity-refused', lambda: module.terminal_rows(progress, dict(prereg, client_sha256=module.PRIOR_CLIENT_SHA), module.CAMPAIGN), 'source identity')

    outputs = []
    for row in rows:
        seconds = 4.0 if row['mode'] == 'axis-cache' else 5.0
        outputs.append({'run': row['run'], 'reported_all_four_outputs_exact': True,
            'timings': {'preview_ready_seconds': seconds, 'tensor_archive_ready_seconds': seconds - .1,
                        'video_decoder_interval_seconds': seconds / 10}})
    pairs = module.paired_results(rows, outputs)
    check('six-balanced-triplets-accepted', pairs['paired_samples'] == 6)
    check('cache-minus-original-negative-for-both-orders', all(
        triple['metrics']['preview_ready_seconds']['cache_minus_original_seconds'] == -1.0
        for triple in pairs['triples']))
    check('fixture-means-combine-both-orders', pairs['fixture_mean_cache_minus_original_seconds'] ==
        {fixture: {'preview_ready_seconds': -1.0, 'tensor_archive_ready_seconds': -1.0000000000000004,
                   'video_decoder_interval_seconds': -0.09999999999999998} for fixture in ('boat', 'marble', 'bird')})
    slower = copy.deepcopy(outputs)
    for row, output in zip(rows, slower):
        output['timings']['preview_ready_seconds'] = 6.0 if row['mode'] == 'axis-cache' else 5.0
    check('cache-regression-positive-for-both-orders', all(
        triple['metrics']['preview_ready_seconds']['cache_minus_original_seconds'] == 1.0
        for triple in module.paired_results(rows, slower)['triples']))
    outputs[0]['reported_all_four_outputs_exact'] = False
    filtered = module.paired_results(rows, outputs)
    check('failed-parity-triplet-excluded', filtered['paired_samples'] == 5)
    check('incomplete-order-pair-not-given-fixture-mean', 'boat' not in filtered['fixture_mean_cache_minus_original_seconds'])

    server = {'pid': 84255, 'boot_id': 'fake-stdlib-only'}
    admission = {'status': 'completed-screen-admitted', 'prior_campaign': module.PRIOR_CAMPAIGN,
        'progress_sha256': module.PRIOR_PROGRESS_SHA, 'identity': server, 'prior_requests': 11,
        'prior_scoped_decodes': 9, 'evidence_sha256s': {module.PRIOR_CAMPAIGN+'/progress.json': module.PRIOR_PROGRESS_SHA}}
    admitted = dict(prereg, prior_screen_admission=admission)
    check('prior-admission-bindings-accepted', module.prior_admission_bindings(admitted, server) == admission['evidence_sha256s'])
    rejects('different-prior-process-refused', lambda: module.prior_admission_bindings(admitted, {'pid': 1}), 'admission identity')
    malformed = copy.deepcopy(admitted)
    malformed['prior_screen_admission']['evidence_sha256s']['../outside.json'] = '0'*64
    rejects('unsafe-prior-evidence-binding-refused', lambda: module.prior_admission_bindings(malformed, server), 'Unsafe prior')
    malformed = copy.deepcopy(admitted)
    malformed['prior_screen_admission']['evidence_sha256s']['raw.safetensors'] = '0'*64
    rejects('raw-prior-evidence-binding-refused', lambda: module.prior_admission_bindings(malformed, server), 'Unsafe prior')
    check('no-native-module-imports', not any(name == 'torch' or name.startswith(('torch.', 'comfy.', 'comfy_kitchen'))
                                            for name in sys.modules))
    print(json.dumps({'status': 'passed-stdlib-confirmation-export-checks', 'checks': checks,
        'export_executed': False, 'live_campaign_read': False, 'native_imports': False,
        'exporter_sha256': module.digest(Path(module.__file__).read_bytes()),
        'test_sha256': module.digest(Path(__file__).read_bytes())}, indent=2))


if __name__ == '__main__':
    main()
