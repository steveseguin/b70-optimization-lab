#!/usr/bin/env python3
"""Portable, read-only audit of generated sparse-state native evidence."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

from audit_semantic_v1 import audit_trial, canonical, digest, local_path, read, require, sha, usage_totals

ORDER = ((8, 'archive'), (8, 'quoted'), (128, 'quoted'), (128, 'archive'))
POLICY = {'context_limit_utf8_bytes': 32768, 'memory_limit_utf8_bytes': 6553,
          'max_ingestion_attempts': 3, 'max_retrieval': 24, 'max_answer_calls': 32,
          'ingestion_generation': {'enable_thinking': False, 'max_tokens': 4096},
          'answer_generation': {'enable_thinking': True, 'reasoning_effort': 'medium', 'max_tokens': 8192}}
PROTOCOL = 'sparse-state-development-v1'


def same(actual, expected, message):
    require(canonical(actual) == canonical(expected), message)


def source_reference(document, size):
    """Replay the actual controlled source, including owner/review/question text."""
    state, states, events, owners, reviews, touched = {}, [], [], {}, {}, set()
    initial = (size + 15)//16
    names = [f'unit{chr(97+i//26)}{chr(97+i%26)}10' for i in range(size)]
    require(len(document['batches']) == initial+16, 'wrong source batch count')
    for n,batch in enumerate(document['batches'], 1):
        require(batch['id'] == n, 'source batch order changed')
        updates = []
        for line in batch['text'].splitlines():
            fields = line.rstrip('.').split()
            if fields[:3] == ['The','balance','of']:
                require(len(fields) == 7 and fields[-1].lstrip('-').isdigit(), 'unrecognized source posting')
                name, amount = fields[3], int(fields[6])
                verb = ' '.join(fields[4:6])
                require(verb in ('is now','increased by','decreased by') and name in names, 'unknown source operation/counter')
                op = {'is now':'set','increased by':'add','decreased by':'sub'}[verb]
                if n <= initial:
                    require(op == 'set' and name not in state, 'initialization must explicitly set new counters')
                else:
                    require(name in state, 'steady update introduces uninitialized counter')
                    touched.add(name)
                require(op == 'set' or amount > 0, 'source arithmetic amount must be positive')
                state[name] = amount if op == 'set' else state[name]+(amount if op == 'add' else -amount)
                updates.append({'counter':name,'op':op,'amount':amount,'quote':line})
            elif ' belongs to counter ' in line:
                ticket,owner = line.rstrip('.').split(' belongs to counter ')
                require(ticket not in owners and owner in names, 'duplicate/invalid source owner')
                owners[ticket] = owner
            elif ' concerns ' in line:
                review,ticket = line.rstrip('.').split(' concerns ')
                require(review not in reviews, 'duplicate review identity')
                reviews[review] = ticket
        require(len(updates) == (min(16, size-16*(n-1)) if n <= initial else 3), 'source posting count differs from design')
        states.append(dict(state)); events.append(updates)
    require(set(state) == set(names) and names[-1] not in touched, 'counter coverage/reserve changed')
    require(len(owners) == len(reviews) == 8 and all(t in owners for t in reviews.values()), 'ownership/review coverage changed')
    answers, subjects, categories = {}, {'current':[],'history':[],'join':[]}, Counter()
    for question in document['questions']:
        require(question['answer_type'] == 'int' and question['id'] not in answers, 'question type/identity changed')
        category = question['category']; require(category in subjects, 'unknown question category')
        text = question['text']
        direct = re.fullmatch(r'What (is|was) the balance of ([a-z]+[0-9]{2}) at the end of batch ([0-9]+)\?', text)
        if direct:
            name,at = direct[2],int(direct[3])
            require(category == ('current' if direct[1]=='is' else 'history'), 'question category differs from source')
            if category == 'current': require(at == len(states), 'current question is not final')
        else:
            join = re.fullmatch(r"Follow (\S+) to its ticket and owner\. What was that owner counter's balance at the end of batch ([0-9]+)\?",text)
            require(join is not None and category == 'join', 'unrecognized question text')
            require(join[1] in reviews, 'question review missing from source')
            name,at = owners[reviews[join[1]]],int(join[2])
        require(1 <= at <= len(states) and name in states[at-1], 'question references unavailable state')
        answers[question['id']] = states[at-1][name]
        subjects[category].append(name); categories[category] += 1
    require(categories == {'current':8,'history':8,'join':8}, 'question counts differ from design')
    require(all(names[-1] in values and any(name in touched for name in values) for values in subjects.values()), 'questions omit untouched or updated counters')
    return states,events,answers


def load_packet(packet):
    """Verify portable frozen files; no tokenizer/runtime execution or downloads."""
    packet = Path(packet); plan = read(packet/'plan.json')
    require(plan.get('schema') == 'sparse-state-plan.v1' and plan.get('protocol') == PROTOCOL, 'wrong sparse packet')
    same({k:plan.get(k) for k in POLICY}, POLICY, 'fixed sparse policy mismatch')
    same(plan['generation'], {'seed':83,'counter_counts':[8,128],'initialization_chunk_max':16,'steady_batches':16,
                             'updates_per_steady_batch':3,'question_counts':{'current':8,'history':8,'join':8}}, 'generation policy mismatch')
    require(plan.get('speed_gate_passed') is False and plan.get('holdout_admitted') is False, 'packet contains a promotion claim')
    require(plan['expected_trials'] == len(plan['trials']) == 4 and
            [(r['counter_count'],r['arm']) for r in plan['trials']] == list(ORDER), 'fixed matrix/order changed')
    for key in ('engine_source_sha256','wrapper_source_sha256'):
        require(isinstance(plan[key],dict) and plan[key] and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v)
                for v in plan[key].values()), 'invalid source pin inventory')
    require(set(plan['engine_source_sha256']) == {'answers.py','diagnostics.py','ledger.py','live.py','tasks.py'}
            and set(plan['wrapper_source_sha256']) == {'budget.py','engine.py','generator.py','runner.py','pinned-engine.json'},
            'source pin inventory is incomplete')
    inventory = {r[k] for r in plan['trials'] for k in ('task_path','document_path')} | {'budget-receipt.json'}
    require(set(plan['files_sha256']) == inventory, 'packet file inventory changed')
    for name,expected in plan['files_sha256'].items():
        path=local_path(packet,name)
        require(path.is_file() and sha(path)==expected, 'packet artifact hash mismatch: '+name)
    tasks={}
    for row in plan['trials']:
        size=row['counter_count']; case=f'sparse-n{size}-seed83'; stem=f'{case}-{row["arm"]}'
        same({k:row[k] for k in ('case_id','task_path','document_path','result_path','native_result_path')},
             {'case_id':case,'task_path':case+'-task.json','document_path':case+'-document.json',
              'result_path':stem+'/result.json','native_result_path':stem+'/native/result.json'}, 'planned path/identity mismatch')
        if case in tasks:
            require(row['task_sha256']==tasks[case]['task_sha256'], 'paired task hash mismatch'); continue
        task=read(packet/row['task_path']); doc=read(packet/row['document_path'])
        require(task['task_sha256']==row['task_sha256']==digest({k:v for k,v in task.items() if k!='task_sha256'}), 'compiled task hash mismatch')
        require(task['schema']=='semantic-development-task.v1' and task['document_id']==doc['id']==case,
                'compiled task/document identity mismatch')
        require(task['source_sha256']==sha(packet/row['document_path']) and task['document_sha256']==digest(doc), 'document source binding mismatch')
        same(task['batches'],doc['batches'],'compiled source changed');same(task['questions'],doc['questions'],'compiled questions changed')
        require(task.get('adjudication_sha256') is None and 'annotation_sources' not in task, 'generated task falsely claims adjudication')
        provenance=task['generated_provenance']
        expected={'kind':'programmatically-generated','generator_seed':83,'counter_count':size,
                  'initialization_batches':(size+15)//16,'initialization_chunk_max':16,
                  'steady_batches':16,'updates_per_steady_batch':3}
        same({k:provenance.get(k) for k in expected},expected,'generated provenance mismatch')
        states,events,answers=source_reference(doc,size)
        same(task['oracle']['after_batch'],states,'private states disagree with actual source replay')
        compiled=[[{'id':f'{n}:{i}',**event} for i,event in enumerate(batch)] for n,batch in enumerate(events,1)]
        same(task['oracle']['events'],compiled,'private events disagree with actual source')
        same(task['oracle']['answers'],answers,'private answers disagree with actual source')
        annotation={'document_id':case,'source_sha256':task['source_sha256'],'answers':answers,
                    'batches':[{'batch_id':n,'events':batch,'state_after':state} for n,(batch,state) in enumerate(zip(events,states),1)]}
        require(task['annotation_sha256']==digest(annotation),'generated reference hash mismatch')
        tasks[case]=task
    budget=read(packet/'budget-receipt.json')
    require(budget['schema']=='sparse-state-budget-receipt.v1' and budget['measurement_kind']=='cpu-oracle-wiring-budget-check', 'budget receipt kind mismatch')
    same(budget['engine_source_sha256'],plan['engine_source_sha256'],'budget engine pins mismatch')
    same(budget['wrapper_source_sha256'],plan['wrapper_source_sha256'],'budget wrapper pins mismatch')
    require(budget['all_reference_prompts_fit'] is True and budget['all_reference_emissions_fit'] is True, 'reference budget did not fit')
    require(len(budget['trials'])==4,'budget matrix incomplete')
    for record,row in zip(budget['trials'],plan['trials']):
        same({k:record[k] for k in ('case_id','arm','task_sha256')},{k:row[k] for k in ('case_id','arm','task_sha256')},'budget row identity mismatch')
        require(set(record['phases'])=={'initialization','steady','answer'},'budget phase coverage mismatch')
        for phase,metrics in record['phases'].items():
            expected_calls=(row['counter_count']+15)//16 if phase=='initialization' else 16 if phase=='steady' else 1
            require(metrics['calls']==expected_calls and metrics['max_reference_prompt_bytes']<=32768
                    and metrics['max_prompt_bytes_with_ascii_memory_allowance']<=32768
                    and metrics['max_reference_response_tokens']<=(8192 if phase=='answer' else 4096), 'budget phase does not fit')
    return plan,tasks


def finite_nonnegative(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def phase_costs(calls, initial):
    groups={name:[] for name in ('initialization','steady','answer')}
    for call in calls:
        require(finite_nonnegative(call['seconds']), 'invalid call duration')
        require(type(call['prompt_bytes']) is int and call['prompt_bytes']==len(canonical(call['messages'])), 'prompt byte count mismatch')
        phase='answer' if call['phase']=='answer' else 'initialization' if call['batch_id']<=initial else 'steady'
        groups[phase].append(call)
    groups['total']=calls
    costs={}
    for name,rows in groups.items():
        usage=usage_totals(rows)
        costs[name]={'calls':len(rows),'client_call_seconds':sum(r['seconds'] for r in rows),
                     'prompt_bytes':sum(r['prompt_bytes'] for r in rows),
                     'prompt_tokens':usage['prompt_tokens'],'completion_tokens':usage['completion_tokens'],
                     'cache_complete':bool(rows) and usage['cached_tokens'] is not None,
                     'cached_tokens':usage['cached_tokens']}
    return costs


def descriptive_pairs(rows,kind):
    pairs={}
    for size in (8,128):
        selected={r['arm']:r for r in rows if r['counter_count']==size}
        eligible=(kind=='model' and len(selected)==2 and all(r.get('quality_passed') is True and
                   r.get('cold_cost_interpretation') is True for r in selected.values()))
        percent=None; threshold=None
        if eligible:
            archive=selected['archive']['total_trial_wall_seconds']; quoted=selected['quoted']['total_trial_wall_seconds']
            require(archive>0,'cannot compare zero elapsed baseline')
            percent=100*(1-quoted/archive);threshold=quoted<=archive*.9
        pairs[str(size)]={'paired_quality':len(selected)==2 and all(r.get('quality_passed') is True for r in selected.values()),
                         'cold_comparison_eligible':eligible,'elapsed_reduction_percent':percent,
                         'at_least_10_percent_lower_elapsed':threshold,
                         'replication_signal':bool(size==128 and eligible and threshold),
                         'speed_gate_passed':False,'holdout_admitted':False,
                         'scope':'Single paired development observation; replication trigger only, no performance conclusion.'}
    return pairs


def audit(output,packet):
    output,packet=Path(output),Path(packet); plan,tasks=load_packet(packet)
    root=output/'diagnostic' if (output/'diagnostic').is_dir() else output
    same(read(root/'plan.json'),plan,'output plan differs from frozen packet')
    summary=read(root/'summary.json')
    require(summary['schema']=='sparse-state-summary.v1' and summary['protocol']==PROTOCOL,'summary identity mismatch')
    kind=summary['measurement_kind'];require(kind in ('stub','model'),'invalid measurement kind')
    identity=summary['server_identity']
    if kind=='stub':
        require(identity is None,'stub output unexpectedly claims a server identity')
    else:
        require(isinstance(identity,dict) and all(isinstance(identity.get(k),str) and identity[k]
                for k in ('endpoint','model','launch_sha256')) and
                re.fullmatch('[0-9a-f]{64}',identity['launch_sha256']), 'model output lacks a bound server identity')
    require(summary['expected_trials']==4 and type(summary['infrastructure_abort']) is bool,'invalid summary coverage')
    require(summary['speed_gate_passed'] is False and summary['holdout_admitted'] is False,'summary promotion claim')
    same(summary['engine_source_sha256'],plan['engine_source_sha256'],'summary engine mismatch')
    inner_plan={**POLICY,'protocol':'semantic-development-live-v1','measurement_kind':kind,
                'source_code_sha256':plan['engine_source_sha256'],'server_identity':summary['server_identity']}
    rows=[];completed_outer=[]
    for item in plan['trials']:
        outer_path=local_path(root,item['result_path']); native_path=local_path(root,item['native_result_path']); task=tasks[item['case_id']]
        base={'case_id':item['case_id'],'counter_count':item['counter_count'],'arm':item['arm'],
              'quality_passed':False,'reference_checks_passed':None,'cold_cost_interpretation':False}
        if not outer_path.exists():
            status='incomplete' if outer_path.parent.exists() else 'unstarted'
            row={**base,'status':status,'reason':'No completed outer receipt'}
            if native_path.exists():
                native=read(native_path)
                require(native.get('resumed') is False and native.get('schema')=='semantic-live-trial.v1'
                        and native.get('case_id')==item['case_id'], 'invalid partial native trial identity')
                row['native_audit']=audit_trial(native_path.parent,native,task,
                    {'document_id':item['case_id'],'arm':item['arm'],'task_sha256':item['task_sha256']},inner_plan)
                row['native_status']=native['status']
            rows.append(row);continue
        outer=read(outer_path)
        require(outer['schema']=='sparse-state-trial.v1' and outer['protocol']==PROTOCOL,'outer trial identity mismatch')
        same({k:outer.get(k) for k in item},item,'outer matrix row mismatch')
        require(outer['measurement_kind']==kind and native_path.is_file() and sha(native_path)==outer['native_sha256'],'native binding/kind mismatch')
        native=read(native_path)
        require(native['resumed'] is False and native['schema']=='semantic-live-trial.v1'
                and native.get('case_id')==item['case_id'], 'invalid native trial kind/resume/identity')
        for key,expected in (('engine_source_sha256',plan['engine_source_sha256']),('wrapper_source_sha256',plan['wrapper_source_sha256']),
                             ('server_identity',summary['server_identity']),('source_sha256',task['source_sha256']),
                             ('generated_provenance',task['generated_provenance']),('native_artifacts',native['artifacts'])):
            same(outer.get(key),expected,'outer provenance mismatch: '+key)
        audited=audit_trial(native_path.parent,native,task,
            {'document_id':item['case_id'],'arm':item['arm'],'task_sha256':item['task_sha256']},inner_plan)
        expected_batches=len(task['batches'])
        reference_checks=(audited['status']=='completed' and audited['correct']==audited['asked']==24 and
            audited['source_delivery_complete'] and audited['checkpoints_checked']==audited['checkpoints_exact']==expected_batches and
            (item['arm']=='archive' or audited['all_accepted_events_exact'] is True and audited['accepted_events']['batches']==expected_batches))
        quality=kind=='model' and reference_checks
        calls=[json.loads(line) for line in (native_path.parent/'calls.jsonl').read_text().splitlines()]
        costs=phase_costs(calls,task['generated_provenance']['initialization_batches'])
        same(outer['phase_costs'],costs,'outer phase cost mismatch')
        cold=kind=='model' and costs['total']['cache_complete'] and costs['total']['cached_tokens']==0
        require(outer['reference_checks_passed'] is reference_checks and outer['quality_passed'] is quality
                and outer['cold_cost_interpretation'] is cold,'outer quality/cold interpretation mismatch')
        require(outer['status']==native['status'] and outer['speed_gate_passed'] is False and outer['holdout_admitted'] is False,'outer status/promotion mismatch')
        wall=native['wall_seconds'];require(finite_nonnegative(wall),'invalid native wall time')
        require(outer['total_trial_wall_seconds']==wall and
                outer['non_call_overhead_seconds']==wall-costs['total']['client_call_seconds'] and
                outer['non_call_overhead_seconds']>=-1e-6,'outer/native time mismatch')
        row={**base,'status':native['status'],'reference_checks_passed':reference_checks,'quality_passed':quality,
             'cold_cost_interpretation':cold,'total_trial_wall_seconds':wall,'phase_costs':costs,
             'non_call_overhead_seconds':outer['non_call_overhead_seconds'],'native_audit':audited,
             'outer_sha256':sha(outer_path),'native_sha256':sha(native_path)}
        rows.append(row);completed_outer.append({**item,'status':row['status'],'quality_passed':quality})
    require([r['case_id']+'-'+r['arm'] for r in completed_outer] ==
            [r['case_id']+'-'+r['arm'] for r in plan['trials'][:len(completed_outer)]], 'later receipt exists after missing earlier trial')
    same(summary['trials'],completed_outer,'summary ordered rows differ from native receipts')
    require(summary['observed_trials']==len(completed_outer),'summary observed count mismatch')
    for status in ('completed','failed'):
        require(summary[status+'_trials']==sum(r['status']==status for r in completed_outer),'summary outcome total mismatch')
    expected_status='failed' if summary['infrastructure_abort'] else 'completed' if len(completed_outer)==4 else 'running'
    require(summary['status']==expected_status,'summary lifecycle mismatch')
    expected_pairs={}
    for item in completed_outer:expected_pairs.setdefault(str(item['counter_count']),[]).append(item)
    same(summary['paired_quality'],{key:len(value)==2 and all(r['quality_passed'] for r in value) for key,value in expected_pairs.items()},'summary pair quality mismatch')
    return {'schema':'sparse-native-audit.v1','measurement_kind':kind,'output':str(output),
            'packet_plan_sha256':sha(packet/'plan.json'),'planned_trials':4,
            'completed_trials':sum(r['status']=='completed' for r in rows),'failed_trials':sum(r['status']=='failed' for r in rows),
            'incomplete_trials':sum(r['status']=='incomplete' for r in rows),'unstarted_trials':sum(r['status']=='unstarted' for r in rows),
            'infrastructure_abort':summary['infrastructure_abort'],'trials':rows,'pairs':descriptive_pairs(rows,kind),
            'speed_gate_passed':False,'holdout_admitted':False,
            'scope':'Generated one-server development screen; CPU reference replay is not external annotation or model evidence.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--packet',type=Path,default=Path(__file__).resolve().parents[2]/'data/2026-10-07-sparse-state-development')
    args=parser.parse_args()
    print(json.dumps(audit(args.out,args.packet),ensure_ascii=False,indent=2))
