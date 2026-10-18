"""Read-only final packet111r audit, with a separate CPU result artifact."""
import json
from source_decision import O,ROOT,P,sha,save


def main():
    from composite_jobs import current,validate,jobs,view,WRAPPER
    path,config=current();validate(config)
    before=json.loads((O/'evidence/p111r-before.json').read_text())
    queues={name:digest for name,digest in before.items() if '/lane-queue/queue-' in name}
    changed=[name for name,digest in before.items() if name not in queues and sha(ROOT/name)!=digest]
    assert not changed,changed
    old=O/'decisions/762f6ebd546b0092.json'
    assert sha(old)=='c9c71d03bf297a0d53acba4e74694848991229e68b805efb25e537eec40216c8'
    from chain_adapter import install
    install()
    from chain_seal import verify
    seal=verify()
    assert seal['bundle_selection']['selection_sha256']==sha(view(config['candidate'])/'selection.json')
    assert not (P/'build/device-cards01-a').exists()
    assert not any((WRAPPER/'evidence'/j['out']).exists() for lane in ('A','B') for j in jobs(config,lane))
    plans=json.loads((O/'p111r-composite-plans.json').read_text())
    assert plans['passed'] and plans['decision_sha256']==sha(path)
    for row in plans['plans']:
        assert row['passed'] and row['jobs']==3
        assert sha(O/('p111r-composite-plan-'+row['lane']+'.log'))==row['log_sha256']
    for leaf in ('chain','composite','smoke','smoke-negative'):
        row=json.loads((O/('evidence/p111r-exec-'+leaf+'.log')).read_text())
        assert row['passed'] and row['device_executed'] is False
    assert '33 passed' in (O/'p111r-final-tests.log').read_text()
    from verify_ready import evaluate
    readiness=evaluate()
    assert readiness['ready'] is False
    assert json.loads((O/'ready.json').read_text())==readiness
    save(O/'p111r-cpu-final.json',dict(passed=True,device_executed=False,
        decision=config['source_rule'],decision_path=str(path.relative_to(ROOT)),decision_sha256=sha(path),
        selected={k:config['candidate'][k] for k in ('other_fusion','target_head')},
        frozen_files_verified=len(before)-len(queues),historical_decision_unchanged=True,
        live_queue_writes_by_this_task=False,
        externally_changed_live_queues=[name for name,digest in queues.items() if sha(ROOT/name)!=digest],
        composite_plans=plans,tests_passed=33,fresh_chain=True,composites_unrun=True,
        launch_limits_passed=True,ready=False,readiness_reason=readiness['reason']))
    print('PASS: frozen files, current decision, chain binding, proposals, 33 tests and exec-limit proofs; readiness remains false')


if __name__=='__main__':main()
