"""Packet-private CPU rehearsal of the actual report entry and decision tails."""
import json, math, shutil, statistics, tempfile
from pathlib import Path
from unittest.mock import patch
from build_engine import P, ROOT, limits
import micro_analyze as a
from test_reports import fixture
import run_micro


def main():
    limits()
    proposal=P.parents[1]/'ops/lane-queue/proposed-p166-micro-B.txt'
    retained=P/'evidence/private-report-cases'
    retained.mkdir(exist_ok=True)
    dependencies=[P/'report_adapter.py',P/'micro_analyze.py',P/'run_micro.py',P/'test_reports.py',
                  P/'evidence/cpu-real-parity.json',P/'evidence/real-oracle.tsv',
                  P/'lineage/packet147-PLAN.md',P/'lineage/packet58h-FEASIBILITY.md']
    assert a.sha(dependencies[-2])==a.sha(P.parent/'packet147-lever-synthesis/PLAN.md')
    assert a.sha(dependencies[-1])==a.sha(P.parent/'packet58h-onecard-mtp/FEASIBILITY.md')
    gate=json.loads((P/'evidence/cpu-real-parity.json').read_text())
    dependencies += [ROOT/r['stdout'] for r in gate['records']]
    cases=[]
    with tempfile.TemporaryDirectory(prefix='packet166-private-report-') as d:
        temporary=Path(d)
        # All reachable decision combinations, including the exact prefill boundary.
        for name,ratio,prefill,mtp in [('both-briefs',1.5,True,True),
                                      ('mtp-only',1.6,False,True),
                                      ('close-both',1.7,False,False)]:
            root=temporary/name;root.mkdir();out=root/'output';out.mkdir()
            (root/'DO-NOT-REPEAT.md').write_text('Synthetic decision rehearsal only\n')
            fixture(out/'samples.jsonl',ratio)
            with patch.object(a,'P',root):
                result=run_micro.report_completed(out)
            assert result['prefill_build_brief'] is prefill
            assert result['mtp_verify_brief'] is mtp
            assert (out/'BUILD-BRIEF.md').exists() is prefill
            assert (out/'MTP-VERIFY-BRIEF.md').exists() is mtp
            closure=(root/'DO-NOT-REPEAT.md').read_text()
            assert ('Fully paired causal M=2 layer micro' in closure) is (not prefill)
            assert ('One-card causal M=2 MTP projection' in closure) is (not mtp)
            for projection in result['projections']:
                m=projection['one_card_mtp_decode']
                assert math.isclose(projection['implied_prefill_tps'],180/ratio)
                assert math.isclose(m['projected_v2_ms'],ratio*1000/31.966820)
                assert math.isclose(m['cycle_ms'],1.794747301+m['projected_v2_ms']+(1-.787401575)*.980923)
            dest=retained/name;dest.mkdir(exist_ok=True)
            for path in out.iterdir():
                if path.name!='samples.jsonl':shutil.copyfile(path,dest/path.name)
            # Stable paths in retained synthetic closures; no live negative index changes.
            (dest/'DO-NOT-REPEAT.md').write_text(closure.replace(str(out),'synthetic-fixture/'+name))
            cases.append(dict(name=name,synthetic_fixture=True,device_measurement=False,
                              ratio=ratio,prefill_brief=prefill,mtp_brief=mtp,
                              serialized_stream_bytes=(out/'samples.jsonl').stat().st_size,
                              samples_digest=a.sha(out/'samples.jsonl')))
        # Rejection through the real report entry must leave all tails untouched.
        invalid=temporary/'invalid';invalid.mkdir()
        fixture(invalid/'samples.jsonl',1.2)
        lines=(invalid/'samples.jsonl').read_text().splitlines()
        summary=json.loads(lines[-1]);summary['cpu_oracle_match']=False
        lines[-1]=json.dumps(summary);(invalid/'samples.jsonl').write_text('\n'.join(lines)+'\n')
        try:run_micro.report_completed(invalid)
        except ValueError as e:assert 'oracle gate' in str(e)
        else:raise AssertionError('invalid oracle accepted')
        assert list(invalid.iterdir())==[invalid/'samples.jsonl']
        # Actual available parent timestamps are replayed without relabeling their schema.
        parent=P.parent/'packet162-iq2-lookup/evidence/enum11-diagnostic-B1/samples.jsonl'
        assert a.sha(parent)=='da1d41370fe90d1368bc3925816583e2ebee77c1e45df457fe91e69ad2811fce'
        dependencies.append(parent)
        rows=a.read_events(parent)
        samples=[r for r in rows if r['kind']=='sample' and r['shape']=='layer0' and r['fixture']==0]
        values=[[a.event_duration(r) for r in samples if r['arm']==arm] for arm in (0,1)]
        assert list(map(len,values))==[200,200]
        assert list(map(statistics.median,values))==[48334,232604]
        replay=temporary/'real-parent';replay.mkdir();shutil.copyfile(parent,replay/'samples.jsonl')
        try:run_micro.report_completed(replay)
        except ValueError as e:
            rejection=str(e);assert 'identity-matched' in rejection
        else:raise AssertionError('wrong-workload parent accepted')
        assert list(replay.iterdir())==[replay/'samples.jsonl']
        # Replay any genuine packet166 device stream already available, if one exists.
        layer_streams=list((P/'evidence').glob('layer-micro-*/samples.jsonl'))
        real_layer=[]
        for stream in layer_streams:
            dest=temporary/('real-'+stream.parent.name);dest.mkdir()
            shutil.copyfile(stream,dest/'samples.jsonl');dependencies.append(stream)
            with patch.object(a,'P',temporary):result=run_micro.report_completed(dest)
            real_layer.append(dict(stream=str(stream.relative_to(ROOT)),decision=result['decision'],mtp_decision=result['mtp_decision']))
    m=a.mtp_projection(1)
    threshold=m['maximum_m2_over_m1_for_2_percent']
    assert math.isclose(a.mtp_projection(threshold)['gain_percent'],2,abs_tol=1e-10)
    t5=m['maximum_m2_over_m1_for_5_percent']
    assert a.mtp_projection(t5-1e-8)['gain_percent']>5>a.mtp_projection(t5+1e-8)['gain_percent']
    # Reproduce packet147's historical budget; do not reuse it on the newer record.
    old=1000*(1+.787401575)/(1.02*29.259764)-1.794747301-(1-.787401575)*.980923
    assert abs(old-57.886273)<.000001
    dependencies += sorted(p for p in retained.rglob('*') if p.is_file())
    receipt=dict(schema='packet166.private-report.v1',passed=True,device_executed=False,
                 actual_entry='run_micro.report_completed -> micro_analyze.evaluate',
                 proposal_sha256=a.sha(proposal),sources={str(p.relative_to(ROOT)):a.sha(p) for p in dependencies},
                 synthetic_cases=cases,invalid_oracle_refused_without_tails=True,
                 actual_parent_replay=dict(sample_counts=list(map(len,values)),median_event_ns=list(map(statistics.median,values)),rejected=True,reason=rejection),
                 actual_packet166_streams=real_layer,
                 scope='No packet166 device stream available' if not real_layer else 'Available packet166 streams replayed',
                 threshold_checks=True,mtp_ratio_for_2_percent=threshold,
                 mtp_v2_plus_feedback_budget_ms=m['v2_plus_feedback_budget_ms_for_2_percent'])
    (P/'evidence/private-report.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),real_parent_rejected=True,real_layer_streams=len(real_layer),ratio_for_2_percent=threshold)))

if __name__=='__main__':main()
