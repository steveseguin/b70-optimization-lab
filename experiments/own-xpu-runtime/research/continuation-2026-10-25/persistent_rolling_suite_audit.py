"""Offline measured12 evidence rules; runtime input never includes expected outputs."""
import hashlib
import math
import json
import os
import stat
from pathlib import Path
import statistics
import struct
from finalize_persistent_rolling_proof import need,identity,token_hash,audit_timing,compare
from persistent_rolling_trace_audit import base


MAX_EVIDENCE=128*1024**2
MAX_LINE=16*1024


def evidence_bytes(path):
    """Larger explicit suite journal budget, with frozen old readers untouched."""
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=MAX_EVIDENCE,
             'bounded regular suite evidence required')
        data=bytearray()
        while len(data)<before.st_size:
            chunk=os.read(fd,min(65536,before.st_size-len(data)));need(chunk,'suite evidence truncated');data.extend(chunk)
        need(not os.read(fd,1) and compare.BUNDLE.identity(before)==compare.BUNDLE.identity(os.fstat(fd))
             ==compare.BUNDLE.identity(os.stat(path,follow_symlinks=False)),'suite evidence changed')
        return bytes(data)
    finally:os.close(fd)


def read(path):return json.loads(evidence_bytes(path),object_pairs_hook=compare.BUNDLE.pairs)


def lines(path):
    raw=evidence_bytes(path);rows=raw.splitlines()
    need(all(0<len(row)<=MAX_LINE for row in rows),'bounded nonempty suite JSONL record required')
    return [json.loads(row,object_pairs_hook=compare.BUNDLE.pairs) for row in rows]


def load_baseline(path):
    path=Path(path);audit=read(path)
    need(audit['schema']=='ownrt.persistent-rolling-baseline-audit.v1' and audit['passed'] is True
         and audit['requests']==12 and audit['output_tokens']==5965,'retained twelve-prompt baseline required')
    sources={}
    for source in audit['sources']:
        p=Path(source['path']);actual=identity(p)
        need(actual['sha256']==source['sha256'] and actual['bytes']==source['bytes'],'baseline source bytes changed')
        sources[p.name]=read(p)
    suite=sources['suite.json'];previous=sources['suite-result.json'];negative=sources['summary.json']
    need(negative['passed'] is True and negative['output_tokens']==5965
         and len(suite['prompts'])==len(audit['rows'])==len(previous['prompts'])==12,
         'accepted prior twelve-prompt arrays required')
    for row,stamp,observed in zip(suite['prompts'],audit['rows'],previous['prompts']):
        ids=row['expected_output_ids'];prompt=row['prompt_tokens']
        need(row['id']==stamp['id']==observed['id'] and ids==observed['output_ids']
             and token_hash(prompt)==stamp['prompt_compact_json_sha256']
             and token_hash(ids)==stamp['output_compact_json_sha256']
             and len(prompt)==stamp['prompt_tokens'] and len(ids)==stamp['output_tokens'],
             'retained token arrays differ from authenticated baseline audit')
        need(type(stamp['cached_tokens_observed']) is int and stamp['cached_tokens_observed']==0
             and row['max_new']==512,'baseline cold cache/cap identity')
        n=len(ids)-1;need(n==stamp['decode_numerator'] and n/stamp['decode_seconds']==stamp['decode_tokens_per_second'],
                         'baseline aggregate interval arithmetic differs')
    need(sum(len(r['expected_output_ids']) for r in suite['prompts'])==5965
         and [(r['id'],len(r['expected_output_ids'])) for r in suite['prompts'] if len(r['expected_output_ids'])<512]==[('customer-email',333)],
         'explicit eleven cap512 plus customer-email333 cohort')
    need(statistics.median(r['decode_tokens_per_second'] for r in audit['rows'])==audit['median_decode_tokens_per_second'],
         'baseline true median differs')
    old_set=path.parent/'persistent-suite-b-proof/final-state-set.json';state=read(old_set);last=suite['prompts'][-1]
    expected=dict(model_sha256=audit['model_identity_sha256'],arithmetic=audit['activation_dtype'],
        prompt_token_sha256=token_hash(last['prompt_tokens']),output_token_sha256=token_hash(last['expected_output_ids']),
        position=len(last['prompt_tokens'])+len(last['expected_output_ids'])-1)
    need(state['input_identity']==expected and expected['position']==571,'retained final state position/token identity differs')
    return dict(audit=audit,rows=suite['prompts'],negative=negative,final_state_path=old_set,final_identity=expected,
                provenance=dict(audit=identity(path),sources=audit['sources'],final_state=identity(old_set)))


def finish_reason(outputs,max_new,eos):
    need(outputs and len(outputs)<=max_new and all(t not in eos for t in outputs[:-1]),'output after EOS or invalid cap')
    if outputs[-1] in eos:return 'eos'
    need(len(outputs)==max_new,'short output without EOS')
    return 'cap'


def validate_suite(plan,suite,terminal,baseline):
    need(plan['schema']=='ownrt.persistent-rolling-plan.v1' and plan['mode']=='persistent-rolling'
         and plan['check_policy']=='measured' and plan['persistent_requests'] is True and plan['use_proposals'] is True
         and plan['dump_each'] is False and plan['suite_prompt_count']==12 and plan['draft_training'] is False
         and all(plan[k] is False for k in ('verify_restore','verify_recursive_restore','verify_provider_survival')),
         'separate measured twelve-request final-state-only policy required')
    need(terminal['schema']=='ownrt.persistent-rolling-result.v1' and terminal['mode']=='persistent-rolling'
         and terminal['check_policy']=='measured' and terminal['passed'] is True and terminal['error'] is None
         and terminal['live_pids']==[] and terminal['returncodes']=={str(s['id']):0 for s in plan['stages']}
         and terminal['actual_provider'] is True and terminal['scripted_oracle_assisted'] is False,'clean actual-provider terminal required')
    need(set(suite)=={'schema','model_identity_sha256','activation_dtype','eos_token_ids','prompts'}
         and suite['schema']=='ownrt.persistent-rolling-inputs.v1'
         and suite['model_identity_sha256']==plan['model_identity_sha256']==baseline['audit']['model_identity_sha256']
         and suite['activation_dtype']==plan['activation_dtype']==baseline['audit']['activation_dtype']=='F32'
         and suite['eos_token_ids']==plan['eos_token_ids'],'strict prompt-only runtime model/arithmetic identity')
    need(suite['prompts']==[{k:r[k] for k in ('id','prompt_tokens','max_new')} for r in baseline['rows']],
         'runtime suite must contain exact prompts/caps only, no offline output reference')
    ident=dict(model=plan['model_identity_sha256'],draft_manifest=plan['draft_model_sha256'],draft_experts=plan['draft_experts'],
        prompt=plan['prompt_tokens'],context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=plan['eos_token_ids'],
        config_sha256=plan['config_sha256'],mode=plan['mode'],check_policy=plan['check_policy'])
    need(hashlib.sha256(__import__('json').dumps(ident,sort_keys=True,separators=(',',':')).encode()).hexdigest()==plan['request_sha256'],
         'process request identity differs')
    required=max(6*(len(r['prompt_tokens'])+r['max_new']-1) for r in suite['prompts'])
    limit=plan.get('ring_trace_limit')
    need(type(limit) is int and required<=limit<=100000,'explicit complete bounded native trace budget required')
    for stage in plan['stages']:
        argv=stage['argv'];flag='--pipeline-ring-trace-limit'
        need(argv.count(flag)==1 and argv.index(flag)+1<len(argv) and argv[argv.index(flag)+1]==str(limit),
             'every native owner must receive exact admitted trace limit')
    reasons=[finish_reason(r['expected_output_ids'],r['max_new'],plan['eos_token_ids']) for r in baseline['rows']]
    need(reasons.count('eos')==1 and reasons[2]=='eos' and reasons.count('cap')==11,'explicit EOS/cap baseline coverage')
    return reasons


def audit_provider(batches,native,replay,records,prompt_length,att,request,epoch):
    contexts=replay['providers'];parent_records={r['row']:r for r in records}
    need(len(batches)==len(native)==len(contexts)==att['provider_trace_records'] and att['provider_trace_omitted']==0,
         'complete actual provider traces required')
    pairs=[]
    for position,(batch,row,ctx) in enumerate(zip(batches,native,contexts),1):
        seed,parent=ctx['seed'],ctx['parent'];head=position>=prompt_length-1;hidden=parent_records[parent['id']]['hidden_sha256'];guesses=batch['guesses']
        need(batch['epoch']==epoch and batch['request_sha256']==request and batch['parent_hidden_sha256']==hidden
             and batch['restored'] is True and batch['speculative_target_use'] is True,'provider independently retained parent hidden identity')
        need((row['sequence'],row['provider_serial'],row['target_pending_depth'],row['seed_row'],row['parent_row'],row['seed_position'],
              row['confirmed_token'],row['fixture'],row['parent_final_ticket'],row['parent_final_commit'],row['hidden_sha256'],row['guesses'],row['restored_position'])
             ==(ctx['sequence'],position,len(ctx['pending']),seed['id'],parent['id'],position,seed['token'],
                max(0,position-prompt_length+2),parent['row_sequence'],parent['accept_sequence'],hidden,guesses,position),
             'native provider differs from raw actual proposal/accepted true-pair witness')
        need(row['mutable_bytes_verified'] is False and row['snapshot_bytes']==(att['provider_private_bytes'] if head else 0),
             'measured provider copy/omitted verification evidence differs')
        pairs.append([position,seed['token'],head,hidden])
    heads=sum(r[2] for r in pairs)
    need(att['provider_commands']==att['provider_position']==att['provider_serial']==len(pairs)
         and att['provider_snapshot_captures']==att['provider_snapshot_restores']==heads
         and att['provider_byteverified_restore_count']==0,'provider operation conservation differs')
    pending={str(d):sum(len(v['pending'])==d for v in contexts) for d in (0,1,2)}
    need(att['provider_pending_borrows']=={k:pending[k] for k in ('1','2')} and att['provider_quiescent_borrows']==pending['0'],
         'actual provider borrow histogram differs')
    return dict(passed=True,pairs=len(pairs),recursive_pairs=heads,pair_sequence_sha256=token_hash(pairs),pending_borrows=pending,
                reference_recursive_predictions_compared=False,scope='Native and controller raw actual-provider agreement; no independent long-cohort recursive prediction reference.')


def distribution(values):
    if not values:return dict(count=0,total=0,minimum=None,median=None,p95=None,maximum=None)
    need(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'finite nonnegative native timing required')
    vals=sorted(values)
    return dict(count=len(vals),total=sum(vals),minimum=vals[0],median=statistics.median(vals),p95=vals[math.ceil(.95*len(vals))-1],maximum=vals[-1])


def work_breakdown(commands,replay,native_provider,prompt_length):
    issued={};stage={};native_ms={k:[] for k in ('canonical_ms','capture_ms','recursive_ms','restore_ms')}
    origin={e['row']['id']:e['proposal'] for e in commands if e['event']=='issued' and e['op']==24 and e['stage']==0}
    for e in commands:
        key=e['stage'],e['sequence']
        if e['event']=='issued':issued[key]=e;continue
        need(key in issued,'timing completion without issued command');start=issued[key]
        if e['row']['position']<prompt_length:continue # Rows producing outputs after first, including discarded decode work.
        owner=stage.setdefault(str(e['stage']),dict(ops={},accepted_by_proposal_depth={'1':0,'2':0},discarded_by_proposal_depth={'1':0,'2':0},rollback_suffix_lengths={'1':0,'2':0}))
        op=owner['ops'].setdefault(str(e['op']),[]);reply=base.REPLY.unpack(bytes.fromhex(e['reply_hex']));op.append(reply[8])
        if e['op']==25 and start['proposal'] is not None:owner['accepted_by_proposal_depth'][str(start['proposal']['depth'])]+=1
    for abort in replay['all_aborts']:
        owner=stage.setdefault(str(abort['stage']),dict(ops={},accepted_by_proposal_depth={'1':0,'2':0},discarded_by_proposal_depth={'1':0,'2':0},rollback_suffix_lengths={'1':0,'2':0}))
        owner['rollback_suffix_lengths'][str(len(abort['discarded']))]+=1
        for row in abort['discarded']:
            p=origin[row['id']];need(p is not None,'discarded row lacks actual proposal origin');owner['discarded_by_proposal_depth'][str(p['depth'])]+=1
    for owner in stage.values():owner['ops']={op:distribution(v) for op,v in owner['ops'].items()}
    for row in native_provider:
        if row['seed_position']<prompt_length:continue
        for key in native_ms:native_ms[key].append(row[key])
    return dict(stage_native_busy_ms=stage,provider_native_ms={k:distribution(v) for k,v in native_ms.items()},
        units='milliseconds',window='Target ROW/resolution position >= prompt length; provider seed >= prompt length. Excludes first output/JIT/prompt, includes wasted speculative work.',
        timing_source='Native Reply.busy_ms raw 64-byte replies and native provider trace component timers',
        utilization_claim=False,coordinator_idle_time_available=False,overlapping_totals_must_not_be_summed_as_wall_time=True)


def timing_summary(rows,baseline,reported):
    rates=[r['timing']['numerator']/r['timing']['denominator_seconds'] for r in rows]
    median=statistics.median(rates);need(reported==median,'outer suite true median differs')
    return dict(candidate_median=median,candidate_pooled_interval_rate=sum(r['timing']['numerator'] for r in rows)/sum(r['timing']['denominator_seconds'] for r in rows),
        baseline_median=baseline['audit']['median_decode_tokens_per_second'],prior_four_stage_median=baseline['negative']['candidate_rates']['median'],
        descriptive_ratio_to_baseline=median/baseline['audit']['median_decode_tokens_per_second'],certified=False,
        candidate_observer='Controller committed-output observations; n-1 / last-first per request, excluding RESET/DUMP.',
        baseline_observer='Retained service full-response decode aggregate; individual completion timestamps absent. No first99 window inference.',
        historical_negative_preserved=True,matched_timing_observer=False)


def load_planner_transition(path,trusted_sha256):
    """Explicit external authority for one reviewed make_plan-only source delta."""
    import ast
    import difflib
    need(path is not None and isinstance(trusted_sha256,str) and len(trusted_sha256)==64,
         'planner transition requires explicit separately supplied digest')
    path=Path(path);receipt_raw=evidence_bytes(path)
    need(hashlib.sha256(receipt_raw).hexdigest()==trusted_sha256,'planner transition digest differs')
    transition=json.loads(receipt_raw,object_pairs_hook=compare.BUNDLE.pairs)
    need(transition['schema']=='ownrt.persistent-rolling-planner-transition.v1' and transition['passed'] is True
         and transition['scope']=='trace-budget-only' and Path(transition['source_path']).name=='persistent_rolling_driver.py',
         'explicit planner-only transition schema required')
    blobs={}
    for key in ('before_source','after_source','patch','cpu_review','independent_review'):
        record=transition[key];p=Path(record['path']);raw=evidence_bytes(p)
        need(len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['sha256'],'planner transition input changed: '+key)
        blobs[key]=raw
    need(transition['after_source']['path']==transition['source_path'],'planner after-source must be actual execution closure path')
    before,after=blobs['before_source'].decode(),blobs['after_source'].decode()
    def other_nodes(source):
        tree=ast.parse(source);planners=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='make_plan']
        need(len(planners)==1,'one existing planner function required')
        return [ast.dump(node,include_attributes=False) for node in tree.body if node is not planners[0]]
    need(other_nodes(before)==other_nodes(after),'planner bridge changed execution/main/import/module code outside make_plan')
    expected=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='before/persistent_rolling_driver.py',tofile='after/persistent_rolling_driver.py'))
    need(expected and blobs['patch']==expected.encode(),'planner canonical source delta differs')
    binding=dict(planner_before_sha256=transition['before_source']['sha256'],planner_after_sha256=transition['after_source']['sha256'],planner_patch_sha256=transition['patch']['sha256'])
    for key in ('cpu_review','independent_review'):
        review=json.loads(blobs[key],object_pairs_hook=compare.BUNDLE.pairs)
        need(review['passed'] is True and all(review.get(k)==v for k,v in binding.items()),'planner review does not bind exact source delta: '+key)
    return dict(**transition,receipt=dict(path=str(path),bytes=len(receipt_raw),sha256=trusted_sha256))


def validate_prerequisite_closure(plan,prior,transition=None):
    """Match native/build and complete pinned execution closure, not geometry alone."""
    need(all(prior[k]==plan[k] for k in ('model_identity_sha256','draft_model_sha256','draft_experts','context','vocab','activation_dtype','boundaries','eos_token_ids')),
         'suite differs from persistent model/geometry qualification')
    def closure(p):
        excluded={p['config'],p['suite']}
        need(excluded<=p['pins'].keys(),'config/suite missing from admitted pins')
        return {k:v for k,v in p['pins'].items() if k not in excluded}
    current=closure(plan);old=closure(prior)
    need(current.keys()==old.keys(),'execution pin inventory changed outside config/suite')
    changes=[key for key in current if current[key]!=old[key]]
    if changes:
        need(transition is not None and changes==[transition['source_path']]
             and old[changes[0]]==transition['before_source']['sha256']
             and current[changes[0]]==transition['after_source']['sha256'],
             'unreviewed controller/scheduler/native/asset pin change')
    for key in current:
        if key.endswith('.py'):need(identity(Path(key))['sha256']==current[key],'current execution source bytes differ')
    receipts=[key for key in current if Path(key).name=='build-receipt.json']
    need(len(receipts)==1,'single pinned native build receipt required')
    build_path=Path(receipts[0]);need(identity(build_path)['sha256']==current[str(build_path)],'native build receipt changed')
    build=read(build_path);binary=build['binary']
    need(build['schema']=='ownrt.engine.build.v1' and binary in current and current[binary]==build['binary_sha256']
         and identity(Path(binary))['sha256']==build['binary_sha256'],'native binary/build identity changed')
    need(len(prior['stages'])==len(plan['stages']),'stage inventory changed')
    def normalize_argv(p,stage):
        args=stage['argv'];need(args.count(binary)==1,'stage executable differs from pinned native build')
        varying={'--max-new':str(p['max_new']),'--seconds':str(p['seconds']),
                 '--pipeline-ring-request-sha256':p['request_sha256'],'--pipeline-ring-check-policy':p['check_policy']}
        if 'ring_trace_limit' in p:varying['--pipeline-ring-trace-limit']=str(p['ring_trace_limit'])
        else:need('--pipeline-ring-trace-limit' not in args,'unrecorded prerequisite trace budget')
        removed=set()
        for flag,value in varying.items():
            need(args.count(flag)==1,'exact variable native flag occurrence: '+flag);i=args.index(flag)
            need(i+1<len(args) and args[i+1]==value,'native variable flag differs from plan: '+flag);removed.update((i,i+1))
        checked=p['check_policy']=='qualification'
        for flag,enabled in (('--pipeline-ring-verify-restore',checked),('--pipeline-ring-recursive-verify-restore',checked and stage['first']),
                             ('--pipeline-ring-verify-provider-survival',checked and stage['first'])):
            need(args.count(flag)==int(enabled),'native policy capability flag differs')
            if enabled:removed.add(args.index(flag))
        root=Path(p['output'])
        def norm(value):
            if value.startswith(str(root)+'/'):return '<output>/'+str(Path(value).relative_to(root))
            return value
        return [norm(v) for i,v in enumerate(args) if i not in removed]
    def environment(p,stage):
        env=dict(stage['environment'])
        for key,suffix in [('SYCL_CACHE_DIR','sycl'),('NEO_CACHE_DIR','neo'),('XDG_CACHE_HOME','xdg')]:
            need(env[key]==str(Path(p['output'])/f"stage{stage['id']}/cache/{suffix}"),'cache path not bound to owner output')
            env[key]='<output>/'+f"stage{stage['id']}/cache/{suffix}"
        return env
    for a,b in zip(plan['stages'],prior['stages']):
        need(all(a[k]==b[k] for k in ('id','first','final','begin','end','bdf','packed_weight_bytes')),
             'native physical/ownership stage geometry changed')
        need(normalize_argv(plan,a)==normalize_argv(prior,b) and environment(plan,a)==environment(prior,b),
             'unqualified native arithmetic/dispatch/environment change')
    return dict(passed=True,native_binary=identity(Path(binary)),build_receipt=identity(build_path),execution_pin_count=len(current),
        changed_source_paths=changes,planner_transition=transition['receipt'] if changes else None,
        allowed_run_differences=['config/suite paths and hashes','output/cache paths','request SHA','seconds/cap','qualification vs measured fixed checks','explicit trace limit'])


def validate_prerequisite_record(summary,plan_path,policy,qualified_summary_path=None):
    need(summary['schema']=='ownrt.persistent-rolling-proof.v1' and summary['passed'] is True and summary['requests']==2
         and summary['check_policy']==policy and summary['all_requests_full_state_parity'] is True
         and summary['provenance_passed'] is True and summary['target_state_exact'] is True
         and summary['draft_state_exact'] is True and summary['output_tokens_exact'] is True,
         'accepted exact two32 prerequisite proof required')
    plan_raw=evidence_bytes(plan_path);bound=summary['original_plan']
    need(hashlib.sha256(plan_raw).hexdigest()==bound['sha256'] and len(plan_raw)==bound['bytes'],
         'prerequisite copied plan not bound to accepted proof summary')
    if policy=='measured':
        need(summary['qualified_reference_parity'] is True and qualified_summary_path is not None,
             'measured prerequisite lacks checked-policy parity')
        actual=identity(Path(qualified_summary_path));bound=summary['qualified_reference']
        need(actual['sha256']==bound['sha256'] and actual['bytes']==bound['bytes'],
             'measured prerequisite refers to another qualification proof')
    return json.loads(plan_raw,object_pairs_hook=compare.BUNDLE.pairs)
