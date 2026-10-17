#!/usr/bin/env python3
"""CPU comparison of two completed glue01 batteries; never a promotion gate."""
import argparse
from pathlib import Path
import re
import battery_client as b


def validate_arm(root, arm):
    result = b.read(root / 'battery-result.json')
    b.require(result['passed'] is True and result['exact'] is True and result['arm'] == arm, arm + ' battery failed')
    b.require(result['timed_suite_first'] is True, 'cold suite order not proved')
    b.require(result['record_sha256'] == b.DEPENDENCIES[b.RECORD], 'record changed')
    required = {b.RESULT, 'report.json', 'quality-current.json', 'recovery-canary.json',
                'metrics-before-suite.prom', 'metrics-after-suite.prom',
                *(f'bench-short-r{i}.json' for i in (1, 2, 3)),
                *(f'exact-depth-{k}k-r{i}.json' for k in (2, 4) for i in (1, 2))}
    b.require(set(result['artifacts']) == required, 'battery artifacts missing or unexpected')
    for name, digest in result['artifacts'].items():
        b.require(Path(name).name == name and b.sha(root / name) == digest, 'battery artifact hash changed: ' + name)
    b.require(b.sha(root / 'report.json') == result['report_sha256'], 'report changed')
    report = b.read(root / 'report.json')
    b.require(report['arm'] == arm and report['exact'] is True, 'report arm/exact mismatch')
    expected_jobs = [j['name'] for j in b.commands(root, 'http://127.0.0.1:19980')]
    b.require([j['name'] for j in report['jobs']] == expected_jobs, 'battery order changed')
    b.require(report['jobs'][1]['returncode'] == 0, 'record checker did not pass')
    b.validate_realistic(b.read(root / b.RESULT), b.read(b.REPO / b.RECORD))
    b.validate_canary(b.read(root / 'recovery-canary.json'))
    b.validate_quality(b.read(root / 'quality-current.json'), report['jobs'][2]['returncode'])
    b.validate_short([b.read(root / f'bench-short-r{i}.json') for i in (1, 2, 3)])
    for depth in (2048, 4096):
        for i in (1, 2):
            b.validate_depth(b.read(root / f'exact-depth-{depth // 1024}k-r{i}.json'), depth)
    recomputed = b.report(b.read(root / b.RESULT),
                          (root / 'metrics-before-suite.prom').read_text(),
                          (root / 'metrics-after-suite.prom').read_text())
    for key, value in recomputed.items():
        b.require(report[key] == value, 'reported metric differs: ' + key)
    return report


def validate_lifecycle(root, arm):
    # Imported only while checking completed evidence, never to launch anything.
    import a367_glue01 as supervisor
    lifecycle = b.read(root / 'glue01-run.json')
    identity = b.read(root / 'identity.json')
    stop = b.read(root / 'stop.json')
    launch = b.read(root / 'launch.json')
    for key in ('passed', 'ready', 'clean_exit', 'gap_complete', 'all_owners_gone'):
        b.require(lifecycle.get(key) is True, arm + ' lifecycle incomplete: ' + key)
    b.require(lifecycle['mock'] is False and identity['mock'] is False, 'mock evidence cannot count')
    b.require(lifecycle['gpu_fault_lines'] == 0, 'run fault evidence')
    b.require(lifecycle['comparison']['exact'] is True, 'supervisor client gate failed')
    b.require(lifecycle['identity_sha256'] == b.sha(root / 'identity.json'), 'identity receipt changed')
    b.require(lifecycle['stop_sha256'] == b.sha(root / 'stop.json'), 'stop receipt changed')
    b.require(identity['arm'] == arm and identity['recipe'] == 'A367', 'arm identity changed')
    b.require(identity['seal_sha256'] == b.sha(supervisor.SEAL) and identity['preregistration_sha256'] == b.sha(supervisor.REG), 'packet identity changed')
    command, environment = supervisor.command_and_environment(root, arm)
    b.require(identity['command'] == command and identity['environment'] == environment, 'undeclared runtime identity change')
    b.require(identity['nice'] == 0 and identity['affinity'] == sorted(supervisor.online_cpus()), 'server scheduling changed')
    b.require(identity['client_command'] == supervisor.client_command(root, arm), 'client launch identity changed')
    b.require(stop['all_owners_gone'] is True and stop['returncode'] == 0, 'unclean stop')
    b.require(stop['completed_unix'] > launch['unix'] and stop['next_launch_not_before_unix'] == stop['completed_unix'] + 305, 'stop timing changed')
    owner = b.read(root / 'owner-window.json')
    b.require(identity['owner_sha256'] == b.sha(root / 'owner-window.json'), 'owner window changed')
    campaign_path = Path(owner['campaign_path'])
    b.require(campaign_path.is_absolute() and b.sha(campaign_path) == identity['campaign_sha256'] == owner['campaign_sha256'], 'campaign hash changed')
    campaign = b.read(campaign_path)
    b.require(campaign['arms'][arm] == str(root), 'campaign output root changed')
    b.require(campaign['seal_sha256'] == identity['seal_sha256'] and campaign['preregistration_sha256'] == identity['preregistration_sha256'], 'campaign packet binding')
    return {'identity': identity, 'launch': launch, 'stop': stop, 'owner': owner}


def compare(control, candidate):
    b.verify_dependencies()
    b.require(control.resolve() != candidate.resolve(), 'arms must have separate output roots')
    reports = {arm: check_arm(root, arm) for arm, root in [('control', control), ('candidate', candidate)]}
    lives = {arm: validate_lifecycle(root, arm) for arm, root in [('control', control), ('candidate', candidate)]}
    left, right = lives['control'], lives['candidate']
    for key in ('campaign_sha256', 'seal_sha256', 'preregistration_sha256', 'host', 'boot_id'):
        b.require(left['identity'][key] == right['identity'][key], 'control/candidate pairing differs: ' + key)
    b.require(right['launch']['unix'] >= left['stop']['next_launch_not_before_unix'], 'candidate launched before 305 second gap')
    b.require(right['owner']['previous_teardown_completed_unix'] == left['stop']['completed_unix'], 'candidate gap not bound to control')
    control_rate = reports['control']['class_balanced_99_interval_median_tok_s']
    candidate_rate = reports['candidate']['class_balanced_99_interval_median_tok_s']
    return {'schema': 'a367-glue01-comparison-v1', 'exact': True, 'battery_passed_both_arms': True,
            'control': reports['control'], 'candidate': reports['candidate'],
            'candidate_over_control': candidate_rate / control_rate,
            'change_percent': 100 * (candidate_rate / control_rate - 1),
            'speed_is_pass_gate': False, 'promotion_eligible': False,
            'operator_gate': 'candidate four-rank byte/input-immutability/graph-replay receipts passed',
            'lifecycle_both_arms_passed': True,
            'fresh_server_determinism_proven': False,
            'interpretation': 'One control and one candidate screen; within ~3% drift closes this small lever. No headline or record from this pair.'}


def check_arm(root, arm):
    """Supervisor hook: complete client gates, independent of speed."""
    b.verify_dependencies()
    report = validate_arm(Path(root), arm)
    if arm == 'candidate':
        import operator_gate
        operator_gate.validate_receipts(Path(root) / 'operator')
    log_path = Path(root) / 'server.log'
    if log_path.is_file():
        report['logged_graph_dispatch'] = graph_dispatch_counts(log_path.read_text(errors='replace'))
        report['logged_graph_dispatch']['server_log_sha256'] = b.sha(log_path)
    return report


def graph_dispatch_counts(text):
    # Same table fields as the retained A118 verifier. CUDAGraphLogging.log()
    # resets each table; summing rows is valid. These are scheduler dispatch
    # counts over the whole window, not per-rank GEMMs or timed-suite-only steps.
    pattern = r'\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([A-Z_]+)\s*\|\s*(\d+)\s*\|'
    rows = [(int(a), int(b_), int(c), mode, int(count)) for a, b_, c, mode, count in re.findall(pattern, text)]
    return {'M1_steps': sum(count for a, padded, padding, mode, count in rows if (a, padded, padding, mode) == (1, 1, 0, 'FULL')) if rows else None,
            'M2_steps': sum(count for a, padded, padding, mode, count in rows if (a, padded, padding, mode) == (2, 2, 0, 'FULL')) if rows else None,
            'scope': 'Logged FULL scheduler dispatches across entire server window, including post-suite battery; not per-rank operator counts.',
            'coverage': 'Only flushed log tables are counted; absent tables mean unavailable.', 'table_rows': len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    b.write(args.output, compare(args.control, args.candidate))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
