#!/usr/bin/env python3
"""Read-only CPU audit of native historical-state evidence, never a quality grader.

Reconstruct states from raw model replies, using a fresh temporary canonical
SQLite ledger for quoted events. No oracle events, states or answers are read.
The supplied task and result are trust roots; hashes establish consistency, not
authenticity against an adversary able to rewrite every artifact and trust root.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile


ENGINE = Path(__file__).parent / 'history_v1'


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def equal(actual, expected, message):
    require(encoded(actual) == encoded(expected), message)


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(directory, task):
    """Return integrity findings, including explicit incomplete-write gaps.

    Failed trials can have coherent evidence. integrity_passed does not imply
    protocol completion or correct answers; quality_passed is always None.
    """
    root = Path(directory).resolve()
    report = {'schema': 'history-snapshot-audit.v1', 'directory': str(root),
              'integrity_passed': False, 'complete_snapshot_evidence': False,
              'quality_passed': None, 'speed_gate_passed': False,
              'issues': [], 'snapshot_write_gaps': [], 'audited_snapshots': 0}
    try:
        _audit(root, task, report)
        report['integrity_passed'] = True
    except (AuditError, OSError, ValueError, TypeError, KeyError, IndexError, sqlite3.Error) as error:
        report['issues'].append(f'{type(error).__name__}: {error}')
    return report


def _audit(root, task, report):
    result = json.loads((root/'result.json').read_bytes())
    require(result['schema'] == 'history-live-trial.v1'
            and result['protocol'] == 'historical-state-development-v1', 'unsupported native identity')
    arm = result['arm']; require(arm in ('archive', 'quoted'), 'unsupported arm')
    require(result.get('retrieval_mode') in ('source-only','history'), 'missing or invalid retrieval mode')
    equal(task['task_sha256'], digest(encoded({k:v for k,v in task.items() if k != 'task_sha256'})), 'task hash mismatch')
    for key in ('task_sha256', 'source_sha256', 'document_id'):
        equal(result[key], task[key], f'native {key} mismatch')
    report.update(status=result['status'], failure_kind=result['failure_kind'], arm=arm,
                  task_sha256=task['task_sha256'], result_sha256=digest((root/'result.json').read_bytes()))
    require(result['status'] in ('completed','failed'), 'invalid native status')
    require(result['resumed'] is False, 'resumed native evidence unsupported')
    for key, value in json.loads((root/'identity.json').read_bytes()).items():
        equal(result[key], value, f'identity differs: {key}')
    artifacts = result['artifacts']
    for name, entry in artifacts.items():
        path = root/name
        require(not Path(name).is_absolute() and path.resolve().is_relative_to(root)
                and not path.is_symlink() and entry['path'] == name, 'unsafe artifact path')
        equal(digest(path.read_bytes()), entry['sha256'], f'artifact digest mismatch: {name}')
    for name in ('calls.jsonl','trace.json','checkpoint.json','answer-session.json'):
        require(name in artifacts, f'missing bound artifact: {name}')
    for name in ('retrieval.jsonl','refusals.jsonl'):
        require(not (root/name).exists() or name in artifacts, f'unbound artifact: {name}')
    calls = lines(root/'calls.jsonl')
    equal(result['calls'], len(calls), 'call count mismatch')
    rows = json.loads((root/'trace.json').read_bytes())['batches']
    equal(result['batches'], rows, 'native trace differs')
    session = json.loads((root/'answer-session.json').read_bytes())
    equal(result['answer_protocol'], session, 'native answer session differs')
    batches = task['batches']
    equal([row['batch_id'] for row in rows], list(range(1,len(rows)+1)), 'trace batches not contiguous')
    require(len(rows) <= len(batches), 'trace exceeds task')
    ingress = [call for call in calls if call['phase'] != 'answer']
    attempts = [(row['batch_id'], entry) for row in rows for entry in row['attempts']]
    require(len(ingress) <= len(attempts), 'extra ingestion calls')
    # A prompt-cap failure happens before ask() records a call, and may leave a
    # final trace attempt without transport. It must never carry a snapshot.
    require(len(attempts)-len(ingress) <= 1, 'missing ingestion call evidence')
    spec = importlib.util.spec_from_file_location('_history_audit_ledger', ENGINE/'ledger.py')
    ledger = importlib.util.module_from_spec(spec); spec.loader.exec_module(ledger)
    equal(result['source_code_sha256']['ledger.py'], digest((ENGINE/'ledger.py').read_bytes()), 'ledger code drift')
    states, receipts, previous, admitted = {}, {}, None, []
    prior_state = {}
    with tempfile.TemporaryDirectory(prefix='history-audit-') as temp:
        with ledger.CanonicalLedger(Path(temp)/'replay.sqlite') as store:
            for batch in batches[:len(rows)]: store.deliver(batch['id'],batch['text'])
            for index, (n, entry) in enumerate(attempts):
                require(1 <= n <= len(batches), 'invalid batch ID')
                if index >= len(ingress):
                    require(result['status']=='failed' and not entry.get('snapshot_receipt'), 'missing call for accepted attempt')
                    continue
                call = ingress[index]
                require(call['phase']==arm and call['batch_id']==n, 'call/attempt order differs')
                payload = json.loads(call['messages'][1]['content'])
                equal(payload['text'], batches[n-1]['text'], 'model source differs from task')
                equal(payload['batch_id'], n, 'model batch ID differs')
                equal(payload['state'],prior_state,'model input state differs from previous admitted state')
                if 'response' in entry:
                    equal(entry['response'],json.loads(call['response']),'trace response differs from raw call')
                valid = False; candidate = None
                try:
                    reply = json.loads(call['response'])
                    require(isinstance(reply,dict), 'invalid reply')
                    memory = reply.get('memory','')
                    require(isinstance(memory,str) and len(memory.encode())<=6553, 'invalid memory')
                    if arm=='archive':
                        require(not set(reply)-{'state','memory'}, 'invalid archive fields')
                        candidate=reply.get('state')
                        require(isinstance(candidate,dict) and all(isinstance(k,str) and type(v) is int for k,v in candidate.items()), 'invalid archive state')
                    else:
                        events=reply.get('events')
                        require(not set(reply)-{'events','memory'} and isinstance(events,list), 'invalid quoted fields')
                        require(all(isinstance(e,dict) and e.get('op') in ('set','add','sub') for e in events), 'invalid quoted operations')
                        store.apply(n,[{**e,'id':f'{n}:{i}'} for i,e in enumerate(events)])
                        candidate=store.metadata()['state']
                    valid=True
                except (ValueError,TypeError,KeyError,ledger.ValidationError,ledger.ConflictError,ledger.OrderError):
                    pass
                if not valid:
                    require(not entry.get('accepted') and 'snapshot_receipt' not in entry, 'invalid reply marked admitted')
                    continue
                require(n not in admitted, 'second valid application of a batch')
                admitted.append(n)
                prior_state=candidate
                if 'snapshot_receipt' not in entry:
                    require(result['status']=='failed' and result['failure_kind']=='infrastructure'
                            and index==len(attempts)-1 and not entry['accepted'], 'unexplained valid-reply snapshot gap')
                    report['snapshot_write_gaps'].append({'batch_id':n,'quoted_apply_committed':arm=='quoted'})
                    continue
                require(entry['accepted'] is True, 'saved snapshot not admitted')
                path=root/f'snapshots/batch-{n}.json'
                require(not path.is_symlink(), 'snapshot is a symlink')
                raw=path.read_bytes(); record=json.loads(raw)
                equal(record['schema'],'history-state-snapshot.v1','snapshot schema differs')
                equal(record['state'],candidate,'snapshot differs from raw accepted state')
                receipt={'schema':'history-state-receipt.v1','batch_id':n,'arm':arm,
                         'source_text_sha256':digest(batches[n-1]['text'].encode()),
                         'raw_response_sha256':digest(call['response'].encode()),
                         'state_sha256':digest(encoded(candidate)), 'previous_snapshot_sha256':previous}
                equal(record['receipt'],receipt,'snapshot provenance differs')
                receipt['snapshot_sha256']=digest(raw)
                equal(entry['snapshot_receipt'],receipt,'trace snapshot receipt differs')
                previous=receipt['snapshot_sha256']; states[n]=candidate;receipts[n]=receipt
            # Read the recorded DB without invoking its writer or touching its WAL.
            with sqlite3.connect((root/'canonical.sqlite').as_uri()+'?mode=ro') as db:
                actual_state={k:None if v is None else int(v) for k,v in db.execute('SELECT counter,value FROM current_state')}
                equal(actual_state,store.metadata()['state'],'recorded SQLite state differs from replay')
                actual_receipts=list(db.execute('SELECT batch_id,delivery_sha256,events_sha256,events_applied,state_sha256 FROM receipts ORDER BY batch_id'))
                expected=[]
                for n in store.metadata()['applied_batches']:
                    r=store.receipt(n);expected.append(tuple(r[k] for k in ('batch_id','delivery_sha256','events_sha256','events_applied','state_sha256')))
                equal(actual_receipts,expected,'recorded SQLite receipts differ from replay')
                deliveries=list(db.execute('SELECT batch_id,text FROM deliveries ORDER BY batch_id'))
                equal(deliveries,[(b['id'],b['text']) for b in batches[:len(rows)]],'recorded canonical sources differ')
    expected_names={f'batch-{n}.json' for n in states}
    actual_names={p.name for p in (root/'snapshots').iterdir()}
    # A write failure can leave one partial file; retain this explicitly as a
    # gap, not as a verified snapshot or successful complete evidence.
    gap_names={f'batch-{g["batch_id"]}.json' for g in report['snapshot_write_gaps']}
    require(expected_names <= actual_names and actual_names <= expected_names|gap_names, 'snapshot inventory mismatch')
    require({p.removeprefix('snapshots/') for p in artifacts if p.startswith('snapshots/')} == actual_names, 'snapshot artifacts inventory differs')
    equal(result['snapshot_count'],len(states),'native snapshot_count differs')
    equal(result['processed_batches'],len(states),'native processed count differs')
    equal([row['batch_id'] for row in rows if row['accepted']],list(states),'admitted batch flags differ')
    _retrievals(root,calls,session,states,receipts,result)
    report['audited_snapshots']=len(states)
    report['complete_snapshot_evidence']=len(states)==len(batches) and not report['snapshot_write_gaps']
    if result['status']=='completed':
        require(report['complete_snapshot_evidence'] and result['protocol_complete'] is True,'completed trial lacks full snapshot evidence')


def _retrievals(root,calls,session,states,receipts,result):
    answer_calls=[c for c in calls if c['phase']=='answer']
    require(len(answer_calls)<=session['calls']<=32 and session['calls']-len(answer_calls)<=1,'answer call accounting differs')
    equal(session['retrievals'],len(session['cache']),'retrieval cache count differs')
    require(session['retrievals']<=24,'retrieval budget exceeded')
    requested=set()
    for call in answer_calls:
        try:
            reply=json.loads(call['response'])
            if reply.get('action')!='state_at':continue
            n=reply['batch_id'];names=reply.get('counters')
            if type(n) is not int or n<=0 or ('counters' in reply and names is None):continue
            if names is not None:
                if not isinstance(names,list) or any(not isinstance(k,str) for k in names):continue
                names=sorted(names)
            requested.add('state_at:'+encoded({'batch_id':n,'counters':names}).decode())
        except (ValueError,TypeError,KeyError,AttributeError):
            continue
    known=[]
    for key, response in session['cache'].items():
        if not key.startswith('state_at:'):continue
        require(result.get('retrieval_mode','history')=='history','source-only trial contains state_at')
        # Runtime cache keys use json.dumps' default ASCII escaping.
        arg=json.loads(key[len('state_at:'):]);n=arg['batch_id'];names=arg['counters']
        require(set(arg)=={'batch_id','counters'} and 'state_at:'+encoded(arg).decode() in requested,
                'cached historical evidence was never requested')
        require(type(n) is int and n in states,'cached snapshot batch unknown')
        if names is not None:
            require(isinstance(names,list) and 1<=len(names)<=256
                    and all(isinstance(k,str) and k and len(k.encode())<=128 for k in names)
                    and len(set(names))==len(names) and names==sorted(names)
                    and len(encoded(names))<=4096,'cached selection violates bounds')
        else:names=sorted(states[n])
        expected={'action':'state_at','batch_id':n,'state':{k:states[n][k] for k in names if k in states[n]},
                  'missing_counters':[k for k in names if k not in states[n]],'receipt':receipts[n],
                  'scope':'Actual accepted state at the end of this batch; may contain model errors.'}
        equal(response,expected,'cached historical evidence differs');known.append(expected)
    evidence=[]
    if (root/'retrieval.jsonl').exists():evidence.extend(lines(root/'retrieval.jsonl'))
    for call in answer_calls:
        payload=json.loads(call['messages'][1]['content'])
        equal(payload['state'],states[max(states)] if states else {},'answer input state differs from accepted state')
        evidence.extend(payload.get('retrieved',[]))
    for response in evidence:
        if response.get('action')=='state_at':
            require(any(encoded(response)==encoded(expected) for expected in known),'returned historical evidence not bound to actual snapshot')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-dir',type=Path,required=True)
    parser.add_argument('--task',type=Path,required=True)
    args=parser.parse_args();report=audit(args.result_dir,json.loads(args.task.read_bytes()))
    print(json.dumps(report,indent=2))
    return 0 if report['integrity_passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
