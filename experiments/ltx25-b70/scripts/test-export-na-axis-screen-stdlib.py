#!/usr/bin/env python3
"""Offline exporter helper checks; never export or read the live campaign."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('na_axis_export_test', LANE / 'scripts/export-na-axis-screen.py')
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
        except (RuntimeError, UnicodeDecodeError) as error:
            check(name, expected in str(error))
            return
        raise AssertionError('Expected refusal: ' + name)
    prereg = {'campaign': module.CAMPAIGN, 'packet_manifest_sha256': module.PACKET_SHA,
        'client_sha256': module.CLIENT_SHA, 'validator_sha256': module.VALIDATOR_SHA,
        'inherited_v3_sha256': module.HELPERS['run-multiblock-screen-v3.py'],
        'frozen_helpers': {name: module.HELPERS[name] for name in
            ('profile-clip.py', 'compare-clip.py', 'run-stability.py')},
        'schedule': module.expected_schedule(module.CAMPAIGN)}
    rows = [dict(row, status='passed') for row in prereg['schedule']]
    passed = {'status': 'passed', 'rows': rows}
    check('complete-passed-terminal-accepted', len(module.terminal_rows(passed, prereg, module.CAMPAIGN)[1]) == 11)
    failed = {'status': 'failed', 'rows': [dict(rows[0], status='failed')]}
    check('partial-failed-terminal-accepted', len(module.terminal_rows(failed, prereg, module.CAMPAIGN)[1]) == 1)
    check('failure-before-first-request-accepted', module.terminal_rows({'status': 'failed', 'rows': []}, prereg, module.CAMPAIGN)[1] == [])
    rejects('running-campaign-refused', lambda: module.terminal_rows(dict(passed, status='running'), prereg, module.CAMPAIGN), 'not terminal')
    rejects('incomplete-passed-campaign-refused', lambda: module.terminal_rows(dict(passed, rows=rows[:-1]), prereg, module.CAMPAIGN), 'Incomplete passed')
    rejects('reordered-attempts-refused', lambda: module.terminal_rows(dict(passed, rows=[rows[1], rows[0], *rows[2:]]), prereg, module.CAMPAIGN), 'differs from plan')
    changed = copy.deepcopy(prereg)
    changed['schedule'][3]['mode'] = 'bare'
    rejects('changed-schedule-refused', lambda: module.terminal_rows(passed, changed, module.CAMPAIGN), 'Invalid bounded')
    rejects('unreviewed-client-refused', lambda: module.terminal_rows(passed, dict(prereg, client_sha256='0'*64), module.CAMPAIGN), 'source identity')
    rejects('duplicate-json-key-refused', lambda: module.unique_json('{"status":"passed","status":"failed"}'), 'Duplicate JSON')
    rejects('nonfinite-json-refused', lambda: module.unique_json('{"time":NaN}'), 'Nonfinite JSON')
    # Execute only the pinned client's pure schedule AST, not its module imports.
    client = (LANE / 'scripts/run-na-axis-screen-v2.py').read_bytes()
    check('reviewed-client-pin-current', module.digest(client) == module.CLIENT_SHA)
    tree = ast.parse(client)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'schedule')
    namespace = {'require': module.require, 're': module.re}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<client-pure-schedule>', 'exec'), namespace)
    check('export-schedule-matches-actual-client-schedule', namespace['schedule'](module.CAMPAIGN) == prereg['schedule'])

    with tempfile.TemporaryDirectory(prefix='ltx-na-export-helpers-') as temp:
        root = Path(temp)
        path = root / 'test.json'
        path.write_bytes(b'{"fixture": true}\n')
        raw, _ = module.read_stable(path)
        check('stable-text-read-preserves-bytes', raw == path.read_bytes())
        rejects('oversized-read-refused', lambda: module.read_stable(path, limit=1), 'exceeds file bound')
        linked = root / 'linked.json'
        linked.symlink_to(path)
        rejects('symlink-read-refused', lambda: module.read_stable(linked), 'Unsafe/symlink')
        binary = root / 'invalid.log'
        binary.write_bytes(b'\xff')
        rejects('nonutf8-text-refused', lambda: module.read_stable(binary)[0].decode('utf-8'), 'decode')
        evidence = root / 'evidence'
        evidence.mkdir()
        text = evidence / 'receipt.json'; text.write_text('{}')
        for name in ('weights.safetensors', 'preview.mp4', 'image.png', 'kernel.so', 'cache.bin'):
            (evidence / name).write_bytes(b'\x00\xff')
        paths = set()
        module.add_tree(paths, evidence)
        check('tree-inventory-excludes-raw-media-binaries', paths == {text})
        with patch.object(module, 'MAX_SCAN_ENTRIES', 1):
            rejects('directory-scan-bound-enforced', lambda: module.add_tree(set(), evidence), 'scan bound')

        fake_root = root / 'fake-root'; fake_root.mkdir()
        fake_server = fake_root / module.SERVER.name; fake_server.mkdir()
        fake_packet = fake_root / module.PACKET.name; fake_packet.mkdir()
        fake_lane = root / 'fake-lane'; fake_lane.mkdir()
        run = prereg['schedule'][0]['run']
        selected_files = [fake_server/'determinism-after-import.json', fake_server/'encoder-placement-test.json',
            fake_server/'components-1-split.json', fake_server/('na-axis-'+run)/'result.json',
            fake_root/'na-axis-migration-10'/'startup.json', fake_root/'requests'/run/'profile.json',
            fake_root/'output/validation'/run/'summary.json']
        for file in selected_files:
            file.parent.mkdir(parents=True, exist_ok=True); file.write_text('{}')
        cache = fake_server/'inductor-cache'/'wrapper.py'
        cache.parent.mkdir(); cache.write_text('raise RuntimeError("not evidence")')
        fake_manifest = {'extension_sha256s': {}, 'files': {}, 'na_axis': {'dependencies': {}}}
        with patch.multiple(module, ROOT=fake_root, SERVER=fake_server, PACKET=fake_packet, LANE=fake_lane):
            paths = module.selected_paths(module.CAMPAIGN, [run], fake_manifest)
        check('startup-node-request-placement-components-selected', set(selected_files) <= paths)
        check('server-generated-cache-excluded', cache not in paths)

    output_rows = []
    for row in rows:
        timing = 4.0 if row['mode'] == 'axis-cache' else 5.0
        output_rows.append({'run': row['run'], 'reported_all_four_outputs_exact': True,
            'timings': {'preview_ready_seconds': timing, 'tensor_archive_ready_seconds': timing - .1,
                        'video_decoder_interval_seconds': timing / 10}})
    pairs = module.paired_results(rows, output_rows)
    check('three-bracketed-pairs-summarized-as-screening', pairs['paired_samples'] == 3 and
        pairs['metric_summaries']['preview_ready_seconds']['median_cache_minus_control_mean_seconds'] == -1.0)
    output_rows[3]['reported_all_four_outputs_exact'] = False
    check('failed-parity-pair-not-summarized', module.paired_results(rows, output_rows)['paired_samples'] == 2)
    check('no-native-module-imports', not any(name == 'torch' or name.startswith(('torch.', 'comfy.', 'comfy_kitchen'))
                                            for name in sys.modules))
    print(json.dumps({'status': 'passed-stdlib-export-helper-checks', 'checks': checks,
        'export_executed': False, 'live_campaign_read': False, 'native_imports': False,
        'exporter_sha256': module.digest(Path(module.__file__).read_bytes()),
        'test_sha256': module.digest(Path(__file__).read_bytes())}, indent=2))


if __name__ == '__main__':
    main()
