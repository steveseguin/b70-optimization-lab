"""Review 15: latest record-lane losses override prior screening wins."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
import source_adapter_review15 as adapter
import orchestrate_review15 as orchestration
from test_composite import one_lane
from test_orchestrate import screens


def bracket(rate=9.72, finish=20, exact=True, choice='head-transpose'):
    rows=one_lane(choice, 'A', rate)['lanes']['A']
    for row in rows:
        row['finished_utc_ns'] += finish
        row['started_utc_ns'] += finish
    rows[1]['exact']=exact
    return dict(kind='confirmation',rows=rows)


@pytest.mark.parametrize('rate,exact,reason', [
    (9.72,True,'not faster than both'),(10.,True,'not faster than both'),
    (10.1,False,'inexact completed'),
])
def test_record_lane_loss_or_inexact_excludes(rate, exact, reason):
    veto=adapter.record_lane_veto('head-transpose',[bracket(rate,exact=exact)])
    assert reason in veto['reason'] and veto['lane']=='A'


def test_latest_completed_record_lane_result_not_first_win():
    old=bracket(10.2,10)
    latest=bracket(9.72,30)
    assert adapter.record_lane_veto('head-transpose',[latest,old])['ratio']==pytest.approx(.972)
    assert adapter.record_lane_veto('head-transpose',[latest,bracket(10.3,40)]) is None
    assert adapter.record_lane_veto('head-transpose',[bracket(9.,choice='other')]) is None
    assert adapter.record_lane_veto('head-transpose',[]) is None


def fake_source(tmp_path, monkeypatch, a_rate=9.72, a_exact=True, a_state='complete'):
    monkeypatch.setattr(adapter,'ROOT',tmp_path)
    monkeypatch.setattr(adapter,'STAGE',tmp_path/'stage')
    wrapper=tmp_path/'wrapper'
    (tmp_path/'stage'/adapter.PACKETS['93']).mkdir(parents=True,exist_ok=True)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    calls=[]
    def jobs(lane,choice=None,direction='B-grid',qualified=None):
        calls.append((lane,direction))
        entries=[]
        for i,c in enumerate(('production','head-transpose','production')):
            out=f'{direction}-{lane}-{i}'
            root=wrapper/'evidence'/out
            root.mkdir(parents=True,exist_ok=True)
            if direction=='B-grid' and not (lane=='A' and a_state=='missing'):
                w=dict(boot_id=boot,passed=True,started_utc_ns=i*3+1,finished_utc_ns=i*3+2)
                if lane=='A' and a_state=='pending' and i==2:
                    w.pop('finished_utc_ns');w['passed']=False
                (root/'window.json').write_text(json.dumps(w))
            entries.append(dict(out=out,choice=c,lane=lane))
        return entries
    def load(j,lane):
        return dict(choice=j['choice'],rate=(a_rate if lane=='A' else 10.086) if j['choice']=='head-transpose' else 10.,
                    exact=a_exact if lane=='A' and j['choice']=='head-transpose' else True,
                    acceptance_counts=[[64,100]])
    def choose(rows,qualified):
        if rows[1]['rate']<=max(rows[0]['rate'],rows[-1]['rate']):
            raise ValueError('no candidate beats both controls')
        return rows[1]
    monkeypatch.setitem(sys.modules,'screen_jobs',SimpleNamespace(verify=lambda:dict(sources={}),
        jobs=jobs,WRAPPER=wrapper,qualified_candidates=lambda:('head-transpose',),choose=choose))
    monkeypatch.setitem(sys.modules,'compare',SimpleNamespace(load=load))
    return calls


@pytest.mark.parametrize('a_rate,a_exact,state,status',[
    (9.72,True,'complete','no-winner'),(10.1,False,'complete','no-winner'),
    (10.,True,'complete','no-winner'),(10.2,True,'complete','winner'),
    (9.72,True,'pending','winner'),(9.72,True,'missing','winner')])
def test_collect_reads_confirmation_and_does_not_wait_for_pending(tmp_path,monkeypatch,a_rate,a_exact,state,status):
    calls=fake_source(tmp_path,monkeypatch,a_rate,a_exact,state)
    result=adapter.collect('93')
    assert ('A','B-grid') in calls and result['status']==status
    if status=='no-winner':
        assert result['record_lane_veto']['lane']=='A'
        assert any('B-grid-A-1/window.json' in k for k in result['receipts'])
    else:
        assert set(result['lanes'])=={'B'}


def test_collect_rechecks_changed_results_at_each_decision(tmp_path,monkeypatch):
    fake_source(tmp_path,monkeypatch,10.2)
    assert adapter.collect('93')['status']=='winner'
    fake_source(tmp_path,monkeypatch,9.72)
    assert adapter.collect('93')['status']=='no-winner'


def test_exclusion_and_its_receipt_hashes_are_in_decision():
    source=screens()
    source['91']=one_lane('route-fast-rec-both-plus','A')
    veto=adapter.record_lane_veto('head-transpose',[bracket()])
    source['93']=dict(status='no-winner',reason=veto['reason'],record_lane_veto=veto,
                      receipts={'rejection/window.json':'a'*64},sources={})
    control,candidate,confirmed=orchestration.select(source)
    config=orchestration.composition(source,control,candidate,confirmed,{}, {})
    assert candidate['head']=='production' and confirmed==['91']
    assert config['excluded_sources']['93']['reason']==veto['reason']
    assert config['evidence_pins']['rejection/window.json']=='a'*64


def test_newly_completed_source_cannot_slip_between_collection_and_decision(tmp_path,monkeypatch):
    import read_screens_review15 as reader
    monkeypatch.setattr(reader,'ROOT',tmp_path)
    source={'93':dict(observed_windows={'window.json':None})}
    reader.require_current(source)
    (tmp_path/'window.json').write_text('{}')
    with pytest.raises(ValueError,match='changed during decision'):
        reader.require_current(source)


def test_completion_during_validation_refuses_freeze_in_all_modes(tmp_path,monkeypatch):
    import read_screens_review15 as reader
    import composite_jobs
    monkeypatch.setattr(reader,'ROOT',tmp_path)
    monkeypatch.setattr(orchestration,'O',tmp_path)
    source={'93':dict(observed_windows={'window.json':None})}
    monkeypatch.setattr(composite_jobs,'validate',lambda config:(tmp_path/'window.json').write_text('{}'))
    with pytest.raises(ValueError,match='changed during decision'):
        orchestration.freeze_decision({},source)
    assert not (tmp_path/'decisions').exists()


def test_decision_only_records_exclusion_without_changing_current_or_proposals(tmp_path,monkeypatch):
    import read_screens_review15 as reader
    import composite_jobs
    source=screens()
    source['91']=one_lane('route-fast-rec-both-plus','A')
    source['93']=dict(status='no-winner',record_lane_veto={'reason':'lane A lost'},reason='lane A lost')
    monkeypatch.setattr(orchestration,'O',tmp_path)
    monkeypatch.setattr(orchestration,'limits',lambda:None)
    monkeypatch.setattr(reader,'collect',lambda:source)
    monkeypatch.setattr(composite_jobs,'validate',lambda config:None)
    monkeypatch.setattr(composite_jobs,'prepare_proposals',lambda *a:pytest.fail('no proposal writes'))
    monkeypatch.setattr(sys,'argv',['orchestrate_review15.py','--decision-only'])
    assert orchestration.main()==0
    assert sorted(p.name for p in tmp_path.iterdir())==['decisions']
    decision=json.loads(next((tmp_path/'decisions').glob('*.json')).read_text())
    assert decision['excluded_sources']['93']['reason']=='lane A lost'


def test_review15_readiness_retains_exclusion_decision(tmp_path,monkeypatch):
    import verify_ready_review15 as verifier
    packet=tmp_path/'packet';packet.mkdir()
    monkeypatch.setattr(orchestration,'O',tmp_path)
    monkeypatch.setattr(verifier,'O',tmp_path)
    monkeypatch.setattr(verifier,'P',packet)
    monkeypatch.setattr(verifier,'sha',lambda path:'x')
    source=screens()
    source['91']=one_lane('route-fast-rec-both-plus','A')
    source['93']=dict(status='no-winner',record_lane_veto={'reason':'lane A lost'},reason='lane A lost')
    control,candidate,confirmed=orchestration.select(source)
    config=orchestration.composition(source,control,candidate,confirmed,{}, {})
    result=dict(passed=True,chain_policy_passed=True,leave_one_out=dict(required=False))
    monkeypatch.setattr(verifier,'matched_composition',lambda config:result)
    row=dict(schema='packet97.ready.v1',ready=True,preparation_passed=True,device_executed=False,
        chain_command=verifier.command(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        pins={'dummy':'x'},checks={k:'x' for k in ('cpu-dry-run','seal','inputs','storage','queue-plan')},
        screens=source,qualified_sources=config['confirmed_levers'],coordinator_pins={},coordinator_closures={},
        selection=candidate,composition=result)
    (tmp_path/'ready.json').write_text(json.dumps(row))
    (packet/'composition-selection.json').write_text(json.dumps(config))
    assert verifier.verify()['ready'] is True
    assert 'device-entry-review15.sh' in verifier.command()


def test_frozen_decisions_and_original_tools_still_match_pins(monkeypatch):
    root=orchestration.ROOT
    for identity in ('d27742791d5b859d','f1e5d7f47fc0fe54'):
        path=orchestration.O/'decisions'/(identity+'.json')
        config=json.loads(path.read_text())
        import composite_jobs
        import orchestrate as original
        assert composite_jobs.identity(config)==identity
        composite_jobs.check_selection(config)
        sources={n:config['qualified_screens'].get(n,dict(status='pending' if n in config['deferred_sources'] else 'no-winner',receipts={},sources={})) for n in original.DIMENSIONS}
        control,candidate,confirmed=original.select(sources)
        candidate,pins=original.apply_pins(candidate,[k+'='+v for k,v in config['coordinator_pins'].items()])
        # Reconstruct the frozen decision with its historical provenance,
        # then check those exact bytes at their explicit archive locations.
        monkeypatch.setattr(original,'source_pins',lambda screens:config['evidence_pins'])
        assert original.composition(sources,control,candidate,confirmed,pins,config['coordinator_closures'])==config
        from historical_pins import preserved_pins
        for name,sha in preserved_pins(config['evidence_pins']).items():
            if '/ops/packet97-orchestration/' in name:
                assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha
