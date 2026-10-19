"""Read-only audit of packet162 evidence; CPU timings never qualify a device arm."""
import hashlib
import json
from pathlib import Path
from analyze import P, ROOT, limits


def summarize(proof):
    assert proof.get('device_executed') is False
    assert {r['compiler'] for r in proof['results']} == {'gnu','intel'}
    reports=[]
    exact=True
    for run in proof['results']:
        rows=run['results']
        fixtures=[r for r in rows if 'columns' in r]
        native=[r for r in rows if r.get('kind')=='native']
        assert [r['fixture'] for r in fixtures]==[0,1,2]
        assert [r['fixture'] for r in native]==[0,1,2]
        assert all((r['columns'],r['rows_per_expert'],r['selected_experts'],r['streams'])==(2560,640,10,2) for r in fixtures)
        for r in fixtures:
            exact &= all(r[k] is True for k in ('logic_chain_bytes_equal','logic_bf16_bytes_equal',
                                                'enum_chain_bytes_equal','enum_bf16_bytes_equal'))
        exact &= all(r['logic_exact'] and r['enum_exact'] and r['invalid_routes_and_tail_checked'] for r in native)
        failures=[r for r in rows if r.get('kind')=='difference' and r['mismatch_count']]
        reports.append(dict(compiler=run['compiler'],finite_fixture_count=2,
                            finite_exact=all(all(r[k] for k in ('logic_chain_bytes_equal','logic_bf16_bytes_equal','enum_chain_bytes_equal','enum_bf16_bytes_equal')) for r in fixtures[:2]),
                            native_output_and_status_exact=all(r['logic_exact'] and r['enum_exact'] for r in native),
                            differences=failures,
                            logic_cpu_ratios=[r['logic_cpu_ratio_diagnostic_only'] for r in fixtures],
                            enum_cpu_ratios=[r['enum_cpu_ratio_diagnostic_only'] for r in fixtures]))
    # Deliberately no device receipt or passing performance inference here.
    return dict(schema='packet162.decision.v1',cpu_strict_exact=bool(exact),
                device_executed=False,device_performance_gate='not measured',
                device_time_ratio=None,build_brief_gate_passed=False,
                decision='close current implementations; retain exact encoding research',compilers=reports)


def main():
    limits()
    proof=json.loads((P/'evidence/cpu-proof.json').read_text())
    for run in proof['results']:
        for name,digest in run['source_hashes'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for name,digest in json.loads((P/'evidence/analysis.json').read_text())['source_hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    result=summarize(proof)
    assert result['cpu_strict_exact'] is False, 'closure identity changed; review instead of silently promoting'
    (P/'evidence/decision.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,cpu_strict_exact=False,build_brief_gate_passed=False)))


if __name__=='__main__':
    main()
