"""Packet-private CPU rehearsal of the actual report entry and both decision tails."""
import json, shutil, tempfile
from pathlib import Path
from unittest.mock import patch
from build_engine import P, ROOT, limits
import micro_analyze as a
from test_analyzer import fixture
import run_micro


def main():
    limits()
    retained = P / 'evidence/private-report-cases'
    retained.mkdir(exist_ok=True)
    dependencies = [P / 'report_adapter.py', P / 'micro_analyze.py', P / 'run_micro.py', P / 'test_analyzer.py',
                    P / 'evidence/oracle-inheritance.json', P / 'evidence/real-oracle.tsv']
    cases = []
    with tempfile.TemporaryDirectory(prefix='packet175b-private-report-') as d:
        temporary = Path(d)
        for name, ratio, eligible in [('eligible-boundary', 0.97, True), ('close-just-above', 0.9705, False),
                                      ('close-regression', 1.25, False)]:
            root = temporary / name; root.mkdir(); out = root / 'output'; out.mkdir()
            (root / 'DO-NOT-REPEAT.md').write_text('Synthetic decision rehearsal only\n')
            fixture(out / 'samples.jsonl', ratio)
            with patch.object(a, 'P', root):
                result = run_micro.report_completed(out)
            assert result['eligible_combined_bundle9'] is eligible
            assert result['decision'] == ('eligible for the combined bundle-9 candidate' if eligible else 'close D1')
            assert (out / 'COMBINED-BUNDLE9-ELIGIBLE.md').exists() is eligible
            closure = (root / 'DO-NOT-REPEAT.md').read_text()
            assert ('D1 same-bit scale-word multicast' in closure) is (not eligible)
            dest = retained / name; dest.mkdir(exist_ok=True)
            for path in out.iterdir():
                if path.name != 'samples.jsonl':
                    shutil.copyfile(path, dest / path.name)
            (dest / 'DO-NOT-REPEAT.md').write_text(closure.replace(str(out), 'synthetic-fixture/' + name))
            cases.append(dict(name=name, synthetic_fixture=True, device_measurement=False, b_over_a=ratio,
                              eligible=eligible, weighted_b_over_a=result['weighted_b_over_a'],
                              samples_digest=a.sha(out / 'samples.jsonl')))
        invalid = temporary / 'invalid'; invalid.mkdir()
        fixture(invalid / 'samples.jsonl', 0.9, summary=dict(cpu_oracle_match=False))
        try:
            run_micro.report_completed(invalid)
        except ValueError as e:
            assert 'oracle gate' in str(e)
        else:
            raise AssertionError('invalid oracle accepted')
        assert list(invalid.iterdir()) == [invalid / 'samples.jsonl']
        # The real packet166 lane-B device stream is a different workload: it must be refused.
        parent = P.parent / 'packet166-m2-layer-micro/evidence/layer-micro-B1/samples.jsonl'
        # Another packet's file: referenced as {name, parent_relpath, parent_digest}, never pinned in sources.
        parents = [dict(name='packet166 lane-B device stream (refused as D1 evidence)',
                        parent_relpath=str(parent.relative_to(ROOT)), parent_digest=a.sha(parent))]
        replay = temporary / 'real-parent'; replay.mkdir(); shutil.copyfile(parent, replay / 'samples.jsonl')
        try:
            run_micro.report_completed(replay)
        except ValueError as e:
            rejection = str(e); assert 'identity-matched' in rejection
        else:
            raise AssertionError('packet166 stream accepted as D1 evidence')
        assert list(replay.iterdir()) == [replay / 'samples.jsonl']
        # A packet175-shaped (D2 warm-ahead) stream must be refused as D1 evidence.
        warm = temporary / 'warm-ahead'; warm.mkdir()
        fixture(warm / 'samples.jsonl', 0.9, warm_in=(1,))
        try:
            run_micro.report_completed(warm)
        except ValueError as e:
            warm_rejection = str(e); assert 'identity-matched' in warm_rejection
        else:
            raise AssertionError('warm-ahead stream accepted as D1 evidence')
        assert list(warm.iterdir()) == [warm / 'samples.jsonl']
    dependencies += sorted(p for p in retained.rglob('*') if p.is_file())
    digests = {lane: a.sha(path) for lane, path in run_micro.PROPOSALS.items()}
    receipt = dict(schema='packet175b.private-report.v1', passed=True, device_executed=False,
                   actual_entry='run_micro.report_completed -> micro_analyze.evaluate',
                   proposal_sha256=digests, sources={str(p.relative_to(ROOT)): a.sha(p) for p in dependencies}, parents=parents,
                   synthetic_cases=cases, invalid_oracle_refused_without_tails=True,
                   packet166_device_stream_rejected=dict(rejected=True, reason=rejection),
                   warm_ahead_stream_rejected=dict(rejected=True, reason=warm_rejection),
                   maximum_b_over_a=a.MAX_RATIO, threshold_checks=True)
    (P / 'evidence/private-report.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(cases), parent_rejected=True)))


if __name__ == '__main__':
    main()
