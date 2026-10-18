#!/usr/bin/env python3
"""Bind the unchanged parent engine, prefix delta, CPU gates and new binaries."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
B = P / 'build'
from storage import digest


def require(ok, message):
    if not ok:
        raise ValueError(message)


def checked():
    import build
    from seal_context import precise
    parent_binding = json.loads((P / 'parent-binding.json').read_text())
    parent = P.parent / parent_binding['parent_packet']
    require(digest(parent / 'build-receipt.json') == parent_binding['seal_sha256'], 'parent seal changed')
    base = json.loads((parent / 'build-receipt.json').read_text())
    require(base['passed'] and base['device_admission_ready'], 'parent preparation incomplete')
    require(digest(P / 'selection.json') == parent_binding['selection_sha256'], 'inherited kernel choice changed')
    require(digest(P / 'oracle-binding.json') == parent_binding['oracle_binding_sha256'], 'oracle binding changed')
    # Verify the runtime delta independently of the build system. Production
    # arithmetic/controller code must remain the parent's exact source bytes.
    originals = json.loads((P / 'base-source-manifest.json').read_text())
    for name, expected in originals['files_sha256'].items():
        if Path(name).suffix in ('.hpp', '.cpp', '.inc', '.bf16') and name != 'mtp.hpp':
            require(base['sources'].get(str((parent/name).relative_to(ROOT))) == expected,
                    'source manifest is not bound to parent seal: ' + name)
            require(digest(P / name) == expected, 'unexpected production-code delta: ' + name)
    current = build.compiled_sources()
    artifacts = {}
    modes = {}
    for mode in ('gnu-host', 'device'):
        receipt_path = P / ('build-' + mode + '-receipt.json')
        row = json.loads(receipt_path.read_text())
        require(row['passed'] and not row['device_executed'], 'build failed')
        require(row['compiled_sources_sha256'] == current, 'stale build: ' + mode)
        for name, expected in row['checked_mirror_sha256'].items():
            require(digest(B / name) == expected, 'compiler mirror changed')
        require(digest(B / mode / 'compile_commands.json') == row['compile_commands_sha256'], 'compiler commands changed')
        for command in json.loads((B / mode / 'compile_commands.json').read_text()):
            precise(command.get('arguments', command.get('command')), mode == 'device')
        for name, expected in row['link_files_sha256'].items():
            require(digest(B / name) == expected, 'link command changed')
            precise((B / name).read_text(), mode == 'device')
        for name, expected in row['artifacts_sha256'].items():
            require(digest(B / name) == expected, 'binary changed: ' + name)
            artifacts[name] = expected
        modes[mode] = digest(receipt_path)
    from p56_cpu_gate import verify as verify_prefix
    prefix_gate = verify_prefix()
    require(prefix_gate['passed'] and not prefix_gate['device_executed'], 'prefix CPU gates incomplete')
    calibration = json.loads((P / 'calibration/selection.json').read_text())
    rule = json.loads((P / 'calibration/preregistration.json').read_text())
    require(calibration['preregistration_sha256'] == digest(P / 'calibration/preregistration.json'), 'calibration rule changed')
    n = calibration['draft_vocab_rows']
    import re
    config = (P / 'p56_config.hpp').read_text()
    for key, value in [('prefix_rows', n), ('full_rows', calibration['full_vocab_rows']), ('row_alignment',rule['row_alignment'])]:
        match = re.search(key + r'\s*=\s*(\d+)', config)
        require(match and int(match.group(1)) == value, 'compiled prefix constant differs: ' + key)
    require(digest(P/'calibration/selection.json') in config, 'compiled calibration hash differs')
    histogram = {int(k): v for k, v in calibration['histogram'].items()}
    total = sum(histogram.values())
    covered = sum(v for k, v in histogram.items() if k < n)
    previous = sum(v for k, v in histogram.items() if k < n - rule['row_alignment'])
    require(total == calibration['tokens'] and covered == calibration['covered_tokens'], 'coverage count changed')
    require(calibration['coverage'] == covered/total and calibration['excluded_tokens'] == total-covered
            and calibration['excluded_fraction'] == (total-covered)/total, 'coverage summary differs')
    require(n % rule['row_alignment'] == 0 and previous*1000 < total*995 <= covered*1000, 'not smallest qualifying prefix')
    from shared_oracle import static_binding
    require(static_binding() == base['shared_oracle'], 'oracle authority differs')
    sources = build.sources()
    for path in P.rglob('*'):
        if path.is_file() and not path.is_symlink() and not set(path.relative_to(P).parts) & {'build', 'oracle', 'submission', '__pycache__', 'evidence', 'analysis'}:
            if path.suffix in ('.py', '.hpp', '.cpp', '.sh') or path.name in ('parent-binding.json','base-source-manifest.json','selection.json','oracle-binding.json','runtime-revision.json') or 'calibration' in path.parts:
                sources[str(path.relative_to(ROOT))] = digest(path)
    for name, expected in base['sources'].items():
        if '/oracle/' in name:
            own_name = name.replace(parent.name, P.name)
            sources[own_name] = expected
        elif not name.startswith(str(parent.relative_to(ROOT))+'/') and name != 'scripts/packet49_submission.py':
            require(digest(ROOT/name) == expected, 'inherited external source changed: '+name)
            sources[name] = expected
    for name in ('experiments/own-xpu-runtime/stage2/packet34-replay-bench/window.py',
                 'experiments/own-xpu-runtime/stage2/packet2/tests/device_window.py',
                 'scripts/submit_localmaxxing_results.py', 'scripts/promotion_evidence.py',
                 'scripts/receipt_qualification.py'):
        sources[name] = digest(ROOT/name)
    # Preserve unchanged fixture expectations and the target oracle identity.
    inherited_fields = ('passed','device_executed','arithmetic','parent_commit','shared_oracle',
                        'oracle_inputs_sha256','oracle_binary_sha256','official_manifest_sha256',
                        'memory_plan','input_sha256','p33_linked_fixture_host_sha256',
                        'p49_qsa_fixture_host_sha256','p49b_expert_fixture_host_sha256',
                        'p49c_fixture_host_sha256','p49d_fixture_host_sha256',
                        'nongemv_fixture_host_sha256_by_context','selection')
    result = {key:base[key] for key in inherited_fields}
    result.update(schema='packet56.scoped-cpu-seal.v1', parent_packet=parent.name,
                  parent_seal_sha256=parent_binding['seal_sha256'], runtime_revision=json.loads((P/'runtime-revision.json').read_text())['runtime_revision'],
                  sources=sources, artifacts_sha256=artifacts, original_artifacts_sha256=artifacts,
                  mode_receipts_sha256=modes, device_admission_ready=True,
                  gates_sha256={'p56-cpu-gates.json':digest(P/'p56-cpu-gates.json')},
                  inherited_gates=dict(parent_seal_sha256=parent_binding['seal_sha256'], scope='Unchanged target kernels and controller; not rerun as packet56 CPU gates'),
                  draft_prefix=dict(draft_vocab_rows=n,full_vocab_rows=calibration['full_vocab_rows'],selection_sha256=digest(P/'calibration/selection.json'),
                                    config_sha256=digest(P/'p56_config.hpp'),coverage=covered/total),
                  scope=dict(base['scope'],prefix_device_exactness_pending=True,full_model_qualification='Coordinator chain required; CPU preparation is not model qualification'))
    return result


def verify():
    row = json.loads((P / 'build-receipt.json').read_text())
    require(row == checked(), 'packet56 source/build/gate binding changed')
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    require(os.getpriority(os.PRIO_PROCESS,0)==19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'helper affinity required')
    start = time.monotonic()
    if args.verify:
        row = verify()
    else:
        require(not (P/'build-receipt.json').exists() and not (B/'device-cards01-a').exists(), 'never overwrite a seal or started chain')
        row = checked()
        (P/'build-receipt.json').write_text(json.dumps(row,indent=2)+'\n')
        from packet56_submission import pin_resealed_packet56
        pin_resealed_packet56(repo=ROOT)
    print(json.dumps(dict(passed=True,device_executed=False,draft_vocab_rows=row['draft_prefix']['draft_vocab_rows'],seconds=time.monotonic()-start)))


if __name__ == '__main__':
    main()
