#!/usr/bin/env python3
"""Portable, read-only audit of sparse replication native evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from audit_semantic_v1 import audit_trial, canonical, digest, local_path, read, require, sha
from audit_sparse_v1 import finite_nonnegative, phase_costs

ORDER = ((83, 'report', 'archive'), (83, 'report', 'quoted'), (97, 'dispatch', 'quoted'), (97, 'dispatch', 'archive'))
POLICY = {'context_limit_utf8_bytes': 32768, 'memory_limit_utf8_bytes': 6553,
          'max_ingestion_attempts': 3, 'max_retrieval': 24, 'max_answer_calls': 32,
          'ingestion_generation': {'enable_thinking': False, 'max_tokens': 4096},
          'answer_generation': {'enable_thinking': True, 'reasoning_effort': 'medium', 'max_tokens': 8192}}
PROTOCOL = 'sparse-state-replication-v1'

ENGINE_SHA256 = {'answers.py': 'e54f797d6c20cde0bd8d40ddf78894ad2004f059ca6ef3535a78b8dbb7ea9bfc', 'diagnostics.py': '6bab40287c483b9cfc41d8c042e88c27989144cb5e36de834747a4eb8b8181d6', 'ledger.py': 'abff2a06690e1f52b4e37479696ba16acb890d630940385ff0d86e13d92c4ef1', 'live.py': '79f9f3a5e251a8221c15da33bbe488c8e8e30278b90674aabdc658f648c56f57', 'tasks.py': 'e15dd0f9e64521b6b143bc872ea17e1f08b27ef5530932b929f9e46d4ec6433f'}
READING_CONVENTIONS = ['Read batches in increasing order. Every stated balance posting takes effect immediately.', 'A question naming an end-of-batch time asks for the state after all postings in that batch.', 'Ticket ownership does not change unless the source explicitly says it changes.']

def same(actual, expected, message):
    require(canonical(actual) == canonical(expected), message)


FILLER = ' '.join(('The clerks sorted the routine records before the courier arrived.'.split()*32)[:320])
ORIGINAL_BYTES = {'document':'c8e2a3034fb45eca7a05d24337a21aaf20bf70f71551c79c1c0c8dbe89bc2a53',
                  'task':'4ec54a927f033352b036a183a2e39cdfe8a55afcc2fc7f21ff4dade465d80c70'}


def source_reference(document, style):
    """Independent token/line reader; no generator, ledger or private key access."""
    require(style in ('report','dispatch'), 'unknown source style')
    names=[f'unit{chr(97+i//26)}{chr(97+i%26)}10' for i in range(128)]
    state,states,events,owners,reviews,touched={ },[],[],{ },{ },set()
    require(len(document['batches'])==24, 'wrong source batch count')
    for n,batch in enumerate(document['batches'],1):
        require(type(batch['id']) is int and batch['id']==n, 'source batch order changed')
        updates=[]; filler_count=0
        for line in batch['text'].splitlines():
            if line==FILLER:
                filler_count+=1;continue
            require(line.endswith('.'), 'unrecognized source line punctuation')
            words=line[:-1].split(' ')
            op=name=amount_text=None
            if style=='report' and len(words)==7 and words[:3]==['The','balance','of']:
                name,amount_text=words[3],words[6]
                op={'is now':'set','increased by':'add','decreased by':'sub'}.get(' '.join(words[4:6]))
            elif style=='dispatch' and len(words)==8:
                if words[:2]==['Dispatch','recorded'] and words[3:7]==['at','a','balance','of']:
                    op,name,amount_text='set',words[2],words[7]
                elif words[:3]==['A','credit','of'] and words[4:7]==['was','posted','to']:
                    op,name,amount_text='add',words[7],words[3]
                elif words[:5]==['Dispatch','posted','a','debit','of'] and words[6]=='against':
                    op,name,amount_text='sub',words[7],words[5]
            if op is not None:
                require(name in names and re.fullmatch(r'-?[0-9]+',amount_text) is not None, 'unknown counter/amount')
                amount=int(amount_text)
                if n<=8:
                    require(op=='set' and name not in state and 100<=amount<=199, 'initialization changed')
                else:
                    require(name in state and 1<=amount<=90, 'steady posting changed')
                    touched.add(name)
                state[name]=amount if op=='set' else state[name]+(amount if op=='add' else -amount)
                updates.append({'counter':name,'op':op,'amount':amount,'quote':line})
            elif len(words)==5 and words[1:4]==['belongs','to','counter']:
                require(n==1 and words[0] not in owners and words[4] in names, 'invalid source ownership')
                owners[words[0]]=words[4]
            elif len(words)==3 and words[1]=='concerns':
                require(n==24 and words[0] not in reviews, 'invalid source review')
                reviews[words[0]]=words[2]
            else:
                raise ValueError('unrecognized source line: '+line[:120])
        require(filler_count==1 and len(updates)==(16 if n<=8 else 3), 'source filler/posting count changed')
        if n<=8:
            require([event['counter'] for event in updates]==names[(n-1)*16:n*16], 'initializer counter order changed')
        else:
            require(len({event['counter'] for event in updates})==3, 'steady counter targets repeated')
        states.append(dict(state));events.append(updates)
    reserve=names[-1]
    require(set(state)==set(names) and reserve not in touched, 'counter coverage/reserve changed')
    subjects=sorted(touched)[:7]+[reserve]
    require(len(subjects)==8, 'insufficient updated subjects')
    require(set(owners)=={f'ticket-n128-{i}' for i in range(8)} and set(owners.values())==set(subjects)
            and reviews=={f'review-n128-{i}':f'ticket-n128-{i}' for i in range(8)}, 'source ownership/review coverage changed')
    answers={};coverage=[];categories=Counter()
    require(len(document['questions'])==24, 'question count changed')
    for position,question in enumerate(document['questions']):
        i=position//3;category=('current','history','join')[position%3]
        require(question['id']==f'{category}-{i}' and question['category']==category
                and question['answer_type']=='int', 'frozen question order/type changed')
        text=question['text']
        if category in ('current','history'):
            prefix='What is the balance of ' if category=='current' else 'What was the balance of '
            require(text.startswith(prefix) and text.endswith('?'), 'unrecognized balance question')
            rest=text[len(prefix):-1].split(' at the end of batch ')
            require(len(rest)==2 and rest[1].isdigit(), 'unrecognized question time')
            name,at=rest[0],int(rest[1])
            require(name==subjects[i] and at==(24 if category=='current' else 9+i*15//7), 'frozen question selection/time changed')
        else:
            prefix='Follow '; middle=" to its ticket and owner. What was that owner counter's balance at the end of batch "
            require(text.startswith(prefix) and text.endswith('?'), 'unrecognized ownership question')
            rest=text[len(prefix):-1].split(middle)
            require(len(rest)==2 and rest[1].isdigit() and rest[0] in reviews, 'unknown review/question time')
            name,at=owners[reviews[rest[0]]],int(rest[1])
            require(rest[0]==f'review-n128-{i}' and at==9+(i*5+2)%16, 'frozen join selection/time changed')
        require(name in states[at-1], 'question references unavailable state')
        answer=states[at-1][name];answers[question['id']]=answer;categories[category]+=1
        if category!='current':
            coverage.append({'id':question['id'],'category':category,'counter':name,'batch_id':at,
                             'value':answer,'final_value':state[name],'differs_from_final':answer!=state[name]})
    require(categories=={'current':8,'history':8,'join':8}, 'category coverage changed')
    require(all(any(row['counter']==reserve for row in coverage if row['category']==category)
                for category in ('history','join')), 'questions omit reserve')
    coverage_record={'historical_questions':16,'differs_from_final':sum(row['differs_from_final'] for row in coverage),
                     'categories':{category:{'asked':8,'differs_from_final':sum(row['differs_from_final'] for row in coverage if row['category']==category)}
                                   for category in ('history','join')},'questions':coverage}
    return states,events,answers,coverage_record


def load_packet(packet):
    """Verify a portable frozen packet without invoking generators or tokenizers."""
    packet=Path(packet);plan=read(packet/'plan.json')
    require(plan.get('schema')=='sparse-replication-plan.v1' and plan.get('protocol')==PROTOCOL, 'wrong replication packet')
    same({key:plan.get(key) for key in POLICY},POLICY,'fixed replication policy mismatch')
    generation={'cases':[{'seed':83,'style':'report','counter_count':128,'origin':'exact-frozen-packet'},
                         {'seed':97,'style':'dispatch','counter_count':128,'origin':'new-programmatic-case'}],
                'initialization_chunk_max':16,'steady_batches':16,'updates_per_steady_batch':3,'filler_words':320,
                'question_counts':{'current':8,'history':8,'join':8},
                'interpretation':'Seed and source style change together; not an isolated style effect.'}
    same(plan['generation'],generation,'generation policy mismatch')
    require(plan.get('speed_gate_passed') is False and plan.get('holdout_admitted') is False,'packet promotion claim')
    require(plan['expected_trials']==len(plan['trials'])==4 and
            [(row['seed'],row['style'],row['arm']) for row in plan['trials']]==list(ORDER),'fixed matrix/order changed')
    for key in ('engine_source_sha256','wrapper_source_sha256'):
        require(isinstance(plan[key],dict) and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v)
                for v in plan[key].values()),'invalid source pin inventory')
    same(plan['engine_source_sha256'],ENGINE_SHA256,'frozen engine identity changed')
    require(set(plan['wrapper_source_sha256'])=={'budget.py','engine.py','generator.py','runner.py','pinned-engine.json','original-source.json'},'wrapper source inventory changed')
    original={'schema':'sparse-replication-original.v1','packet_relative_to_experiment':'data/2026-10-07-sparse-state-development',
              'files_sha256':{f'sparse-n128-seed83-{kind}.json':value for kind,value in ORIGINAL_BYTES.items()}}
    same(plan['original_source'],original,'original source provenance mismatch')
    inventory={row[key] for row in plan['trials'] for key in ('task_path','document_path')}|{'budget-receipt.json'}
    require(set(plan['files_sha256'])==inventory,'packet file inventory changed')
    for name,expected in plan['files_sha256'].items():
        path=local_path(packet,name)
        require(path.is_file() and sha(path)==expected,'packet artifact hash mismatch: '+name)
    tasks={};coverage={}
    for row in plan['trials']:
        seed,style=row['seed'],row['style'];case='sparse-n128-seed83' if seed==83 else 'sparse-n128-seed97-dispatch'
        stem=case+'-'+row['arm']
        expected={'case_id':case,'counter_count':128,'seed':seed,'style':style,'arm':row['arm'],
                  'task_path':case+'-task.json','document_path':case+'-document.json',
                  'result_path':stem+'/result.json','native_result_path':stem+'/native/result.json'}
        same({key:row.get(key) for key in expected},expected,'planned path/identity mismatch')
        if case in tasks:
            require(row['task_sha256']==tasks[case]['task_sha256'],'paired task hash mismatch');continue
        if seed==83:
            for kind,expected_sha in ORIGINAL_BYTES.items():
                require(sha(packet/row[kind+'_path'])==expected_sha,'original report bytes changed')
        task=read(packet/row['task_path']);doc=read(packet/row['document_path'])
        require(task['task_sha256']==row['task_sha256']==digest({k:v for k,v in task.items() if k!='task_sha256'}),'compiled task hash mismatch')
        require(task['schema']=='semantic-development-task.v1' and task['document_id']==doc['id']==case,'task/document identity mismatch')
        require(task['source_sha256']==sha(packet/row['document_path']) and task['document_sha256']==digest(doc),'source document binding mismatch')
        for key in ('pair_id','variant','batches','questions'):
            same(task[key],doc[key],'compiled source field changed: '+key)
        same(task['reading_conventions'],READING_CONVENTIONS,'reading conventions changed')
        require(task.get('adjudication_sha256') is None and 'annotation_sources' not in task,'generated task falsely claims adjudication')
        expected={'kind':'programmatically-generated','generator_seed':seed,'counter_count':128,
                  'initialization_batches':8,'initialization_chunk_max':16,'steady_batches':16,
                  'updates_per_steady_batch':3,'untouched_counter':'unitex10'}
        same({key:task['generated_provenance'].get(key) for key in expected},expected,'generated provenance mismatch')
        if seed==97:require(task['generated_provenance'].get('style')=='dispatch','dispatch provenance changed')
        states,events,answers,case_coverage=source_reference(doc,style)
        same(task['oracle']['after_batch'],states,'private states disagree with actual source')
        same(task['oracle']['events'],[[{'id':f'{n}:{i}',**event} for i,event in enumerate(batch)] for n,batch in enumerate(events,1)],'private events disagree with actual source')
        same(task['oracle']['answers'],answers,'private answers disagree with actual source')
        annotation={'document_id':case,'source_sha256':task['source_sha256'],'answers':answers,
                    'batches':[{'batch_id':n,'events':batch,'state_after':state} for n,(batch,state) in enumerate(zip(events,states),1)]}
        require(task['annotation_sha256']==digest(annotation),'generated reference hash mismatch')
        tasks[case]=task;coverage[case]=case_coverage
    same(plan['historical_coverage'],coverage,'historical question coverage differs from actual source')
    budget=read(packet/'budget-receipt.json')
    require(budget['schema']=='sparse-replication-budget-receipt.v1' and budget['measurement_kind']=='cpu-oracle-wiring-budget-check','budget receipt kind mismatch')
    same(budget['engine_source_sha256'],plan['engine_source_sha256'],'budget engine mismatch')
    same(budget['wrapper_source_sha256'],plan['wrapper_source_sha256'],'budget wrapper mismatch')
    require(re.fullmatch('[0-9a-f]{64}',budget['tokenizer_sha256']) is not None,'invalid tokenizer identity')
    require(budget['all_reference_prompts_fit'] is True and budget['all_reference_emissions_fit'] is True,'reference budget did not fit')
    require(len(budget['trials'])==4,'budget matrix incomplete')
    for record,row in zip(budget['trials'],plan['trials']):
        same({key:record[key] for key in ('case_id','arm','task_sha256')},{key:row[key] for key in ('case_id','arm','task_sha256')},'budget row identity mismatch')
        require(set(record['phases'])=={'initialization','steady','answer'},'budget phase coverage mismatch')
        for phase,metrics in record['phases'].items():
            require(all(type(value) is int and value>=0 for value in metrics.values()),'invalid budget metric type/value')
            require(metrics['calls']==(8 if phase=='initialization' else 16 if phase=='steady' else 1)
                    and metrics['max_reference_prompt_bytes']<=32768
                    and metrics['max_prompt_bytes_with_ascii_memory_allowance']<=32768
                    and metrics['max_reference_response_tokens']<=(8192 if phase=='answer' else 4096),'budget phase does not fit')
    return plan,tasks


def descriptive_pairs(rows,kind):
    """Keep original-case repetition separate from joint seed/style transfer."""
    pairs={}
    for case,role in (('sparse-n128-seed83','original-task-repeat'),('sparse-n128-seed97-dispatch','new-seed-and-style-transfer')):
        selected={row['arm']:row for row in rows if row['case_id']==case}
        quality=len(selected)==2 and all(row.get('quality_passed') is True for row in selected.values())
        eligible=kind=='model' and quality and all(row.get('cold_cost_interpretation') is True for row in selected.values())
        percent=threshold=None
        if eligible:
            archive=selected['archive']['total_trial_wall_seconds'];quoted=selected['quoted']['total_trial_wall_seconds']
            require(archive>0,'cannot compare zero elapsed baseline')
            percent=100*(1-quoted/archive);threshold=quoted<=archive*.9
        pairs[case]={'role':role,'paired_quality':quality,'cold_comparison_eligible':eligible,
                     'elapsed_reduction_percent':percent,'at_least_10_percent_lower_elapsed':threshold,
                     'original_task_repeat_signal':bool(role=='original-task-repeat' and eligible and threshold),
                     'new_case_transfer_signal':bool(role=='new-seed-and-style-transfer' and eligible and threshold),
                     'speed_gate_passed':False,'holdout_admitted':False,
                     'scope':'One pair in this fresh-server campaign; no pooled estimate or general performance conclusion.'}
    return pairs


def audit(output,packet):
    output,packet=Path(output),Path(packet); plan,tasks=load_packet(packet)
    root=output/'diagnostic' if (output/'diagnostic').is_dir() else output
    same(read(root/'plan.json'),plan,'output plan differs from frozen packet')
    summary=read(root/'summary.json')
    require(summary['schema']=='sparse-replication-summary.v1' and summary['protocol']==PROTOCOL,'summary identity mismatch')
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
    same(summary['historical_coverage'],plan['historical_coverage'],'summary historical coverage mismatch')
    inner_plan={**POLICY,'protocol':'semantic-development-live-v1','measurement_kind':kind,
                'source_code_sha256':plan['engine_source_sha256'],'server_identity':summary['server_identity']}
    rows=[];completed_outer=[]
    for item in plan['trials']:
        outer_path=local_path(root,item['result_path']); native_path=local_path(root,item['native_result_path']); task=tasks[item['case_id']]
        base={'case_id':item['case_id'],'counter_count':item['counter_count'],'seed':item['seed'],'style':item['style'],'arm':item['arm'],
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
        require(outer['schema']=='sparse-replication-trial.v1' and outer['protocol']==PROTOCOL,'outer trial identity mismatch')
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
    for item in completed_outer:expected_pairs.setdefault(item['case_id'],[]).append(item)
    same(summary['paired_quality'],{key:len(value)==2 and all(r['quality_passed'] for r in value) for key,value in expected_pairs.items()},'summary pair quality mismatch')
    return {'schema':'sparse-replication-native-audit.v1','measurement_kind':kind,'output':str(output),
            'packet_plan_sha256':sha(packet/'plan.json'),'planned_trials':4,
            'completed_trials':sum(r['status']=='completed' for r in rows),'failed_trials':sum(r['status']=='failed' for r in rows),
            'incomplete_trials':sum(r['status']=='incomplete' for r in rows),'unstarted_trials':sum(r['status']=='unstarted' for r in rows),
            'infrastructure_abort':summary['infrastructure_abort'],'trials':rows,'pairs':descriptive_pairs(rows,kind),
            'speed_gate_passed':False,'holdout_admitted':False,
            'historical_coverage':plan['historical_coverage'],
            'scope':'One fresh-server development replication packet; report83 repeats an earlier case, dispatch97 changes seed and style together. No generalization or promotion claim.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--packet',type=Path,default=Path(__file__).resolve().parents[2]/'data/2026-10-07-sparse-state-replication')
    args=parser.parse_args()
    print(json.dumps(audit(args.out,args.packet),ensure_ascii=False,indent=2))
