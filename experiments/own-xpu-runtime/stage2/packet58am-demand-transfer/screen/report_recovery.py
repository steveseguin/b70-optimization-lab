"""CPU-only recovery of the completed amd smoke; never rewrite device receipts."""
import json, sys, time, shutil
from pathlib import Path
import suite_driver as D
import window as W

P = Path(__file__).resolve().parent.parent
SMOKE = P/'screen/evidence/card0-demand-amd-fixed/smoke'
POLICY = P/'REPORT-RECOVERY-POLICY.md'
read, sha, require = D.read, D.sha, D.require


def report_completed():
    """The actual report operations used by suite_driver and window, unpatched."""
    out = SMOKE/'WSCREEN'
    window = read(out/'window.json')
    require(window['returncode'] == 0 and not window['child_still_running'], 'native child not completed')
    require(window['teardown_confirmed_before_reporting']['passed'] and
            window['lane_admission']['devices_drained'], 'device drain not proven')
    require(len(window['stop_reasons']) == 1 and
            'lineage/fixtures/58c-supervisor/source-manifest.json' in window['stop_reasons'][0],
            'not the registered report-only failure')
    import queue_runner as Q
    for stage in ('K1a', 'K1b'):
        Q.verify_success(stage, SMOKE, 0, 0)
    driver = read(out/'run/receipt.json')
    require(driver['passed'] and driver['safe_to_exit'], 'driver not complete')
    for name, key in [('summary.json','summary_sha256'), ('demand-summary.json','demand_summary_sha256')]:
        require(sha(out/'run'/name) == driver[key], 'original driver report changed')
    manifest = D.oracle_inputs()
    require(read(out/'run/suite-manifest.snapshot.json') == manifest, 'oracle manifest changed')
    D.verify_lookup_views(out/'run', 'smoke')
    summary = D.summarize_bracket(out/'run', 'smoke', manifest, 'overlap')
    observation = W.postload_observation(out, window['memory_admission']['plan'], window['memory_admission'])
    summary.update(report_recovery=True, postload_memory=observation,
                   original_window_passed=False, recovered_utc_ns=time.time_ns())
    require([v['label'] for v in summary['views']] == ['S0', 'S1'], 'both smoke views required')
    require(all(len(v['requests']) == 12 and all(r['exact_oracle'] for r in v['requests'])
                for v in summary['views']), 'incomplete exact smoke')
    return summary


def regenerate():
    target = SMOKE/'report-regeneration.json'
    require(not target.exists(), 'report already recovered')
    originals = {str(f.relative_to(SMOKE)):sha(f) for f in SMOKE.rglob('*') if f.is_file()}
    summary = report_completed()
    # Run the unchanged demand reader in its own namespace (analyze module names clash).
    import subprocess
    result = subprocess.run([sys.executable, '-B', str(P/'read_run.py'), str(P/'proposals/smoke.json'),
                             str(SMOKE/'WSCREEN/run/run'), '--output', str(SMOKE/'recovered-demand-summary.json')],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    require(result.returncode == 0, result.stderr)
    demand = read(SMOKE/'recovered-demand-summary.json')
    require(demand['exact'] and demand['same_parent'], 'recovered demand not exact')
    D.save(SMOKE/'recovered-summary.json', summary)
    require(all(sha(SMOKE/n) == h for n,h in originals.items()), 'original device evidence changed')
    report_sources = {str(f.relative_to(P)):sha(f) for f in (Path(__file__), P/'read_run.py', P/'analyze.py', POLICY,
        P/'screen/suite_driver.py', P/'screen/window.py', P/'screen/legacy_memory_plan.py',
        P/'screen/suite_metrics.py', P/'screen/resident_receipt.py')}
    fixture = read(P/'lineage/report-fixtures.json')
    report_sources.update({r['destination']:r['sha256'] for r in fixture['files']})
    oracle_sources = {str(D.ROOT/n):h for n,h in read(P/'screen/oracle-binding.json')['files_sha256'].items()}
    for entry in D.oracle_inputs()['prompts']:
        base = D.ORACLE/'results'/entry['prompt_id']
        for leaf in ('receipt.json','result.json','validation.json'):
            oracle_sources[str(base/leaf)] = sha(base/leaf)
    for prompt in D.METRICS.PROMPT_CLASSES:
        path=P.parent/f'packet58aj-onecard-resident/evidence/card0-58aj-a/WS128/run/run/{prompt}/result.json'
        oracle_sources[str(path)]=sha(path)
        path=P/f'inputs/{prompt}/oracle-64.txt'
        report_sources[str(path)]=sha(path)
    for path in (P/'proposals/smoke.json', P/'lineage/report-fixtures.json', P/'screen/oracle-binding.json',
                 P/'screen/host-admission/tensor-census.json', P/'screen/compare_bracket.py', P/'screen/views.py'):
        report_sources[str(path)]=sha(path)
    for name,digest in oracle_sources.items():
        snapshot=P/'lineage/report-oracle-inputs'/Path(name).relative_to(D.ROOT)
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        if not snapshot.exists(): shutil.copyfile(name,snapshot)
        require(sha(snapshot)==digest,'oracle snapshot changed')
        report_sources[str(snapshot)]=digest
    D.save(target, dict(schema='packet58ame.offline-report-regeneration.v1', passed=True,
        device_executed=False, model_payload_read=False, original_files=originals,
        report_sources={str(P/n):h for n,h in report_sources.items()}, oracle_inputs=[dict(original=n,
            snapshot=str(P/'lineage/report-oracle-inputs'/Path(n).relative_to(D.ROOT)),sha256=h) for n,h in oracle_sources.items()],
        reports={n:sha(SMOKE/n) for n in ('recovered-summary.json','recovered-demand-summary.json')},
        original_failure_preserved=True, exact_views=['S0','S1'], exact_requests=24,
        arithmetic=D.ARITHMETIC, smoke_precondition_satisfied=True,
        owner_policy_sha256=sha(POLICY), overhead_qualified=demand['overhead_qualified'],
        legacy_smoke_passed=demand['smoke_passed'], policy='owner packet58ame brief: recovered exact S0/S1 suffices for v5',
        regenerated_utc_ns=time.time_ns()))
    shutil.copyfile(target,P/'lineage/recovered-smoke-report.json')
    print('Recovered real report: S0 12/12 exact; S1 12/12 exact; original receipts unchanged')


def verified_smoke():
    require(sha(SMOKE/'report-regeneration.json') == sha(P/'lineage/recovered-smoke-report.json'),
            'recovery differs from sealed historical snapshot')
    recovery = read(SMOKE/'report-regeneration.json')
    require(recovery['passed'] and recovery['device_executed'] is False and recovery['exact_requests'] == 24,
            'invalid recovery')
    for name, digest in recovery['original_files'].items():
        require(sha(SMOKE/name) == digest, 'original smoke changed: '+name)
    for name, digest in recovery['report_sources'].items():
        require(sha(P/name) == digest, 'recovery source changed: '+name)
    for item in recovery['oracle_inputs']:
        require(sha(item['original']) == sha(item['snapshot']) == item['sha256'],
                'oracle original/snapshot changed: '+item['original'])
    for name, digest in recovery['reports'].items():
        require(sha(SMOKE/name) == digest, 'recovered report changed: '+name)
    require(sha(POLICY) == recovery['owner_policy_sha256'], 'owner recovery policy changed')
    report = read(SMOKE/'recovered-demand-summary.json')
    require(report['exact'] and report['same_parent'] and report['job_name'] == read(P/'proposals/smoke.json')['job_name'],
            'wrong recovered smoke identity')
    return dict(report, recovered_exact_smoke_precondition=True,
                report_regeneration_sha256=sha(SMOKE/'report-regeneration.json'))

if __name__ == '__main__':
    regenerate()
