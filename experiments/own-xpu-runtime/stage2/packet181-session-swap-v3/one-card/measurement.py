"""Strict-512 accounting. Oracle prefix equality is separate from performance."""
import hashlib,json,math,statistics
from pathlib import Path
import suite_metrics as M
EOS=(248044,248046)
IDS=tuple(M.PROMPT_CLASSES)
ARITHMETIC='iq3-p49-split32-v1'
def require(ok,message):
 if not ok:raise ValueError(message)
def digest(tokens):return hashlib.sha256(json.dumps(tokens,separators=(',',':')).encode()).hexdigest()
def stream_check(result,expected=None):
 """Only presence/format, cache identity, termination and exactness in-run."""
 require(result.get('passed') is True and result.get('arithmetic')==ARITHMETIC,'request identity')
 tokens=result.get('tokens');rows=result.get('timing_rows')
 require(isinstance(tokens,list) and tokens and all(type(t)is int and 0<=t<248320 for t in tokens),'token stream absent or malformed')
 require(isinstance(rows,list) and len(rows)==len(tokens),'timing stream count')
 stamps=[r['completed_monotonic'] for r in rows]
 require(all(type(t)in (int,float) and math.isfinite(t) for t in stamps) and all(b>a for a,b in zip(stamps,stamps[1:])),'invalid timing stream')
 require(result.get('cached_tokens')==0,'cache reuse')
 cap=result.get('requested_max_new',result.get('requested_output_tokens'))
 require(type(cap)is int and 0<len(tokens)<=cap,'response cap')
 require(not any(t in EOS for t in tokens[:-1]),'tokens after EOS')
 require(len(tokens)==cap or tokens[-1] in EOS,'incomplete response')
 start=result.get('request_start_monotonic');end=result.get('request_end_monotonic')
 require(type(start)in(int,float) and type(end)in(int,float) and math.isfinite(start) and math.isfinite(end) and start<=stamps[0]<=stamps[-1]<=end,'request timing endpoints')
 checked=0
 if expected is not None:
  require(isinstance(expected,list) and expected,'oracle missing')
  checked=min(len(tokens),len(expected));require(tokens[:checked]==expected[:checked],'packet49 oracle prefix mismatch')
  if len(tokens)<len(expected):require(tokens[-1]in EOS and tokens==expected[:len(tokens)],'premature completion')
 return dict(passed=True,tokens_compared=checked,oracle_cap=128,full_output_exact=expected is not None and checked==len(tokens),beyond_oracle_tokens=max(0,len(tokens)-checked),beyond_oracle_status='pending fresh-load determinism; not oracle-exact' if len(tokens)>checked else 'none')
def check_file_stream(path):
 """Require actual completed JSONL rows; never demand data by a clock deadline."""
 path=Path(path);require(path.is_file() and path.stat().st_size>0,'missing stream: '+path.name)
 count=0
 with path.open() as f:
  for line in f:
   row=json.loads(line);require(isinstance(row,dict),'stream row must be an object');count+=1
 require(count>0,'empty stream');return count

def request(result,prompt_tokens,prompt_id,expected=None):
 check=stream_check(result,expected)
 cap=result.get('requested_max_new',result.get('requested_output_tokens'))
 metrics=M.request_metrics(result,len(prompt_tokens),cap,'none',result['request_start_monotonic'],result['request_end_monotonic'],True)
 # Whole-request wall rate includes the actual native tail through completion.
 elapsed=result['request_end_monotonic']-result['request_start_monotonic']
 metrics.update(wall_tok_s=len(result['tokens'])/elapsed,wall_rate_definition='output events / (request_end - request_start); includes prompt and complete generation, excludes load/reset/teardown',
  passed=True,prompt_id=prompt_id,prompt_class=M.PROMPT_CLASSES.get(prompt_id,'prefill'),tokens=result['tokens'],repeat=1,
  prompt_token_sha256=digest(prompt_tokens),oracle_check=check,exact_oracle=check['full_output_exact'])
 metrics['full_completion_definition']='(N-1)/(tN-t1) over non-EOS generated events; natural EOS and cap-limited results reported separately'
 if prompt_id=='prefill512':
  ms=result.get('prefill_ms',result.get('prompt_wall_ms'))
  require(len(prompt_tokens)==512 and type(ms)in(int,float) and math.isfinite(ms) and ms>0,'512-input prefill timing missing')
  # Primary prefill rate is request TTFT based, not an invented device duration.
  ttft_ms=1000*(result['timing_rows'][0]['completed_monotonic']-result['request_start_monotonic'])
  require(math.isfinite(ttft_ms) and ttft_ms>0,'positive request TTFT required')
  warm=result.get('warmup')
  if warm is not None:
   require(warm.get('prompt_id')==IDS[0] and warm.get('prompt_token_sha256')!=digest(prompt_tokens),'warm-up identity')
   require(warm.get('completed_before_prefill')is True and warm.get('state_reset_before_prefill')is True and warm.get('cached_tokens')==0 and warm.get('request_count_before_prefill')==1,'warm-up/reset evidence')
   hashes=[warm.get('receipt_sha256'),*warm.get('reset_sha256',[])]
   require(len(hashes)>=2 and all(isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h) for h in hashes),'warm-up/reset receipt hashes')
  metrics['prefill']=dict(input_tokens=512,users=1,elapsed_ms=ttft_ms,tok_s=512000/ttft_ms,
    timing_definition='512 / request TTFT seconds: request_start_monotonic through first generated-token completed_monotonic; excludes model load; includes host and first-token work and any reset inside the native request interval; not HTTP TTFT',
    request_start_boundary=result.get('request_start_boundary','legacy native request boundary'),
    native_prompt_loop_ms=ms,native_prompt_loop_tok_s=512000/ms,
    native_prompt_loop_definition='native prompt-loop wall time through first generated token, including final prompt position and output head; not device-only time',
    prefill_phase_device_ms=None,prefill_phase_device_status='not available: unchanged token-timing build does not expose an isolated device prefill phase',
    construction='first 512 tokenizer IDs from one unrepeated real-document excerpt, no special tokens',cached_tokens=0,oracle_covered=False,
    warmup=warm,measurement_temperature='warm-runtime/cold-prompt' if warm else 'cold-first-request or legacy evidence; not packet165 warm proof')

 return metrics

def aggregate(rows,prefill=None,identity=None,reference=None):
 require([r['prompt_id'] for r in rows]==list(IDS),'complete fixed suite in registered order required')
 require(all(r.get('passed') is True and r.get('cached_tokens')==0 for r in rows),'failed/cacheful request')
 if prefill and prefill.get('prefill',{}).get('warmup'):
  warm=prefill['prefill']['warmup']
  require(warm['prompt_token_sha256']==rows[0]['prompt_token_sha256'],'warm-up must be the first registered suite input')
 result=M.aggregate(rows);result.pop('raw_payload_fields',None)
 failures=[]
 if any(r.get('requested_max_new')!=512 for r in rows):failures.append('requested cap must be 512 for every prompt')
 if any(r.get('finish_reason') not in ('eos','length') for r in rows):failures.append('natural completion or response cap missing')
 if any(not r.get('metric_window_eligible') for r in rows):failures.append('every prompt must supply the first 100 generated events')
 if {r['prompt_class'] for r in rows}!=set(M.PROMPT_CLASSES.values()):failures.append('varied classes incomplete')
 result.update(schema='packet165.warm-prefill.v1',passed=True,kind='full512',requests=rows,request_count=12,
  requested_max_new=512 if not any(r.get('requested_max_new')!=512 for r in rows) else None,
  arithmetic=ARITHMETIC,kv_dtype='BF16',context=4096,prompt_kv_response_reuse=False,cache_zero=True,
  strict512=not failures,realistic_final_gate=dict(passed=not failures,failures=failures,scope='performance workload only; independent quality gate below'),
  prefill=prefill.get('prefill') if prefill else None,prefill_request=prefill,identity=identity,
  quality=dict(oracle_identity=ARITHMETIC,oracle_cap=128,all_available_oracle_tokens_exact=all(r.get('oracle_check',{}).get('passed') for r in rows),
   full_output_oracle_exact=all(r.get('oracle_check',{}).get('full_output_exact') for r in rows),
   beyond_128='pending fresh-load determinism; never oracle-exact',fresh_process_determinism_checked=False,no_quality_loss_decision=False),
  full_natural_completion_statistics=M.stats(r.get('full_natural_completion_tok_s') for r in rows),
  full_cap_limited_statistics=M.stats(r.get('full_cap_limited_tok_s') for r in rows),submission_eligible=False,
  no_speed_verdict_until_two_fresh_loads=True)
 if reference is not None:
  require(identity==reference.get('identity'),'fresh repeat identity differs')
  require(reference.get('strict512')is True and result['strict512'],'fresh repeat needs complete strict512 attempts')
  require([r['prompt_token_sha256'] for r in rows]==[r['prompt_token_sha256'] for r in reference['requests']],'repeat input identity')
  require([r['tokens'] for r in rows]==[r['tokens'] for r in reference['requests']],'fresh-process output differs')
  require(prefill is not None and reference.get('prefill_request') is not None,'prefill repeat missing')
  require(prefill['prompt_token_sha256']==reference['prefill_request']['prompt_token_sha256'] and prefill['tokens']==reference['prefill_request']['tokens'],'prefill fresh repeat differs')
  result['quality'].update(fresh_process_determinism_checked=True,beyond_128='determinism-checked across two fresh loads; not oracle-exact')
  result['fresh_load_repeat']=dict(passed=True,request_count=13,scope='all emitted tokens, including EOS/cap and prefill response')
  result['no_speed_verdict_until_two_fresh_loads']=False
 return result

def checkpoint_check(save,restore1,restore2,reference,expected,k,m):
 """Restart-and-continue exactness plus repeat determinism (design 7.1/7.2/7.3)."""
 for leg in (save,restore1,restore2):stream_check(leg)
 require(len(save['tokens'])==k and not any(t in EOS for t in save['tokens']),'checkpoint save must complete K tokens without EOS')
 require(restore1['tokens']==restore2['tokens'],'repeat restore determinism')
 require(len(restore1['tokens'])==m,'restore continuation length')
 merged=save['tokens']+restore1['tokens']
 require(merged==reference.get('tokens',[])[:k+m],'merged checkpoint stream differs from the uninterrupted fresh-process reference')
 combined=dict(save)
 combined.update(tokens=merged,requested_max_new=k+m,
  timing_rows=save['timing_rows']+restore1['timing_rows'],
  request_start_monotonic=save['request_start_monotonic'],request_end_monotonic=restore1['request_end_monotonic'])
 oracle=stream_check(combined,expected)
 rows=reference.get('timing_rows',[]);require(len(rows)>=k,'reference timing stream short')
 cold_prefix_ms=1000*(rows[k-1]['completed_monotonic']-reference['request_start_monotonic'])
 return dict(passed=True,device_executed=False,merged_tokens=k+m,reference_tokens_compared=k+m,
  repeat_restore_identical=True,save_eos_free=True,oracle_check=oracle,
  cold_prefix_ms=cold_prefix_ms,
  cold_prefix_definition='uninterrupted reference request start through its K-th generated token (cold prefill plus decode of the same prefix), same prompt same binary',
  restore_continuation_wall_ms=1000*(restore1['request_end_monotonic']-restore1['request_start_monotonic']))

# ---------------------------------------------------------------- packet180 comparators
LIFECYCLE_CONTRACT='v1.2+p180'
LIFECYCLE_OPERATIONS=['same-generation-resume','append','restore-then-save']

def first_divergence(actual,expected):
 """First index where two token streams differ (a length difference counts), else None."""
 actual=list(actual);expected=list(expected);n=min(len(actual),len(expected))
 for i in range(n):
  if actual[i]!=expected[i]:return dict(index=i,actual=actual[i],expected=expected[i],actual_length=len(actual),expected_length=len(expected))
 if len(actual)!=len(expected):
  return dict(index=n,actual=actual[n] if n<len(actual) else None,expected=expected[n] if n<len(expected) else None,
   actual_length=len(actual),expected_length=len(expected))
 return None

def compare_streams(label,actual,expected):
 """Exact equality; the record keeps the first divergent index and BOTH streams."""
 d=first_divergence(actual,expected)
 return dict(label=label,passed=d is None,compared=min(len(actual),len(expected)),first_divergence=d,
  actual_tokens=list(actual),expected_tokens=list(expected))

def lifecycle_turn(spec,here):
 """The appended turn T: a fixed EOS-free slice of a suite input, re-derived from its source file."""
 turn=spec['turn'];source=list(map(int,(Path(here)/turn['source']).read_text().split()))
 tokens=source[turn['start']:turn['stop']]
 require(tokens==turn['tokens'],'lifecycle turn differs from its recorded source slice')
 require(len(tokens)>=64 and not any(t in EOS for t in tokens),'lifecycle turn must be at least 64 EOS-free tokens')
 return tokens

def lifecycle_input(prompt,generated,turn,spec):
 """NEW = P + gen[0:K] + T: the saved history P + gen[0:K-1], the pending token gen[K-1], then T."""
 require(len(generated)==spec['K'] and not any(t in EOS for t in generated),'save leg must produce K EOS-free tokens')
 new=list(prompt)+list(generated)+list(turn)
 require(len(new)+spec['M1']+spec['M2']<=spec['context'],'lifecycle input plus decode exceeds the context allocation')
 return new

def manifest_semantics(manifest,tokens,small_blobs=None):
 """Python mirror of the engine's token-state cross-checks; reads packet179 v1 and packet180 manifests."""
 import struct
 ts=manifest['token_state'];N=ts['position'];eos=manifest['geometry']['eos'];problems=[]
 if ts['length']!=N:problems.append('length != position')
 if len(tokens)!=N:problems.append('tokens.bin length != position')
 if not 1<=ts['prompt_length']<=N:problems.append('prompt_length outside the processed prefix')
 history=[tokens[N-2] if N>=2 else eos,tokens[N-1]] if len(tokens)==N and N>=1 else None
 if list(ts['token_history'])!=history:problems.append('token_history != last two processed tokens')
 for name,want in (('position',N),('next_token',ts['next_token']),('token',history[1] if history else None),('error',0)):
  if small_blobs and name in small_blobs and struct.unpack('<i',small_blobs[name])[0]!=want:problems.append(name+' blob disagrees')
 if small_blobs and 'token_history' in small_blobs and list(struct.unpack('<2q',small_blobs['token_history']))!=history:
  problems.append('token_history blob disagrees')
 if sum(b['bytes'] for b in manifest['blobs'])!=manifest['measurements']['save_bytes']:problems.append('save_bytes != sum of blob bytes')
 return dict(passed=not problems,problems=problems,position=N,pending_token=ts['next_token'],
  blobs_checked=sorted(small_blobs) if small_blobs else [])

def p179_identity(observed,reference):
 """Row a: every request's full output equals packet179 row a's (relinked binary, unchanged arithmetic)."""
 rows=[];ok=True
 for pid,ref in reference['prompts'].items():
  got=observed.get(pid)
  cmp=compare_streams(pid,got if got is not None else [],ref['tokens'])
  passed=got is not None and cmp['passed'] and digest(got)==ref['output_token_digest']
  ok&=passed
  rows.append(dict(prompt_id=pid,passed=passed,tokens=len(got or []),first_divergence=cmp['first_divergence'],
   actual_tokens=None if passed else cmp['actual_tokens'],expected_tokens=None if passed else cmp['expected_tokens']))
 extra=sorted(set(observed)-set(reference['prompts']))
 return dict(passed=bool(ok and not extra and len(rows)==13),compared_prompts=len(rows),unexpected_prompts=extra,rows=rows,
  reference_binary_sha256=reference['binary_sha256'],
  scope='full output streams of all 13 requests (12 suite prompts + prefill512) versus packet179 row a')

def lifecycle_check(results,manifests,tools,spec,prompt,turn,p179_tokens,oracle):
 """Row b gates. Returns a receipt and never raises on a gate failure, so both streams are kept."""
 K,M1,M2=spec['K'],spec['M1'],spec['M2'];ids=spec['checkpoint_ids']
 sv,x,y,r,x2=(results[k] for k in ('save-s1','append-s2','resume-s2','reference','append-s2b'))
 gates={};problems=[]
 def gate(name,ok,detail=None):
  gates[name]=dict(passed=bool(ok),detail=detail)
  if not ok:problems.append(name)
 for leg,res in results.items():
  try:stream_check(res);gate('stream '+leg,True)
  except (ValueError,KeyError,TypeError) as error:gate('stream '+leg,False,str(error))
 gate('save K tokens EOS-free',len(sv['tokens'])==K and not any(t in EOS for t in sv['tokens']))
 save_p179=compare_streams('save-s1 vs packet179 row-a '+spec['prompt_id']+' [0:K]',sv['tokens'],list(p179_tokens)[:K])
 gate('save == packet179 row a [0:K]',save_p179['passed'],save_p179['first_divergence'])
 try:
  oracle_check=stream_check(sv,oracle)
  gate('save oracle-128 prefix',oracle_check['tokens_compared']==min(len(sv['tokens']),len(oracle)))
 except (ValueError,KeyError,TypeError) as error:
  oracle_check=None;gate('save oracle-128 prefix',False,str(error))
 R=list(r['tokens'])
 append_cmp=compare_streams('append (2) vs one-shot reference (4) [0:M1]',x['tokens'],R[:M1])
 gate('append == reference [0:M1]',append_cmp['passed'],append_cmp['first_divergence'])
 if len(R)>M1:
  chain_cmp=compare_streams('resume of S2 (3) vs one-shot reference (4) [M1:M1+M2]',y['tokens'],R[M1:M1+M2])
  gate('restore-then-save chain == reference [M1:M1+M2]',chain_cmp['passed'],chain_cmp['first_divergence'])
 else:
  chain_cmp=None
  gate('restore-then-save chain == reference [M1:M1+M2]',False,'not evaluable: the reference stopped naturally after '+str(len(R))+' <= M1 tokens')
 repeat_cmp=compare_streams('append repeat (5) vs append (2)',x2['tokens'],x['tokens'])
 gate('append repeat identical',repeat_cmp['passed'],repeat_cmp['first_divergence'])
 N1=len(prompt)+K-1;L=len(prompt)+K+len(turn)
 def rec(res):return res.get('checkpoint') or {}
 s1=rec(sv).get('save') or {}
 gate('save record',rec(sv).get('restore') is None and s1.get('checkpoint_id')==ids['S1'] and s1.get('position')==N1
      and s1.get('pending_token')==sv['tokens'][-1],s1)
 for leg,res,sid in (('append-s2',x,ids['S2']),('append-s2b',x2,ids['S2b'])):
  rr=rec(res).get('restore') or {};ss=rec(res).get('save') or {}
  gate(leg+' restore record',rr.get('operation')=='append' and rr.get('checkpoint_id')==ids['S1'] and rr.get('saved_prefix_length')==N1
       and rr.get('appended_length')==len(turn) and rr.get('input_length')==L and rr.get('pending_token')==sv['tokens'][-1]
       and rr.get('manifest_sha256')==manifests[ids['S1']]['sha256']
       and isinstance(rr.get('restore_ms'),(int,float)) and isinstance(rr.get('append_prefill_ms'),(int,float)),rr)
  gate(leg+' save record',ss.get('checkpoint_id')==sid and ss.get('parent_checkpoint_id')==ids['S1']
       and ss.get('position')==L+len(res['tokens'])-1 and ss.get('pending_token')==res['tokens'][-1],ss)
 ry=rec(y).get('restore') or {}
 gate('resume restore record',ry.get('operation')=='same-generation-resume' and ry.get('checkpoint_id')==ids['S2']
      and ry.get('saved_prefix_length')==L+len(x['tokens'])-1 and ry.get('pending_token')==x['tokens'][-1]
      and ry.get('appended_length')==0 and ry.get('append_prefill_ms') is None and rec(y).get('save') is None,ry)
 gate('reference is a fresh run',rec(r).get('restore') is None and rec(r).get('save') is None)
 m1,m2,m2b=(manifests[ids[k]] for k in ('S1','S2','S2b'))
 for cid,m in ((ids['S1'],m1),(ids['S2'],m2),(ids['S2b'],m2b)):
  mm=m['manifest']
  gate('manifest identity '+cid,mm.get('format')=='ownrt.session-checkpoint.v1' and mm.get('label')=='experimental'
       and mm.get('contract')==LIFECYCLE_CONTRACT and mm.get('operations')==LIFECYCLE_OPERATIONS and mm.get('checkpoint_id')==cid)
  gate('manifest semantics '+cid,m['semantics']['passed'],m['semantics']['problems'])
 gate('S1 lineage save',m1['manifest']['lineage']=={'operation':'save','parent':None})
 gate('S1 position',m1['manifest']['token_state']['position']==N1 and m1['manifest']['token_state']['prompt_length']==len(prompt))
 for cid,m in ((ids['S2'],m2),(ids['S2b'],m2b)):
  gate('lineage '+cid,m['manifest']['lineage']=={'operation':'restore-then-save','parent':{'checkpoint_id':ids['S1'],'manifest_sha256':m1['sha256']}})
 gate('S2 position',m2['manifest']['token_state']['position']==L+len(x['tokens'])-1 and m2['manifest']['token_state']['prompt_length']==L)
 strip=lambda m:[(b['name'],b['bytes'],b['sha256'],b['slice']) for b in m['manifest']['blobs']]
 gate('S2 == S2b saved state (every blob sha256, token state)',strip(m2)==strip(m2b) and m2['manifest']['token_state']==m2b['manifest']['token_state'])
 for cid in (ids['S1'],ids['S2'],ids['S2b']):
  t=tools.get('metadata-'+cid,{});o=t.get('stdout_object') or {}
  gate('inspect-metadata '+cid,t.get('returncode')==0 and t.get('stdout_lines')==1 and t.get('stderr_json_lines') and o.get('ok') is True
       and o.get('mode')=='metadata' and o.get('manifest')==manifests[cid]['manifest'] and o.get('manifest_sha256')==manifests[cid]['sha256']
       and (o.get('verified') or {}).get('blobs_verified') is None,{k:o.get(k) for k in ('ok','mode','error')})
 for cid in (ids['S2'],ids['S2b']):
  t=tools.get('full-'+cid,{});o=t.get('stdout_object') or {};mm=manifests[cid]['manifest'];v=o.get('verified') or {}
  gate('inspect-full '+cid,t.get('returncode')==0 and t.get('stdout_lines')==1 and t.get('stderr_json_lines') and o.get('ok') is True
       and o.get('mode')=='full' and v.get('blobs_verified')==len(mm['blobs'])
       and v.get('blob_bytes_verified')==mm['measurements']['save_bytes']+4*mm['token_state']['position'],{k:o.get(k) for k in ('ok','mode','error','verified')})
 t=tools.get('delete-'+ids['S2b'],{});o=t.get('stdout_object') or {}
 gate('delete '+ids['S2b'],t.get('returncode')==0 and o.get('deleted') is True and t.get('directory_removed') is True and t.get('lock_removed') is True,
      {k:o.get(k) for k in ('ok','deleted','reason','error')})
 def ms(res,key):return (rec(res).get('restore') or {}).get(key)
 restore_path=None if ms(x,'restore_ms') is None or ms(x,'append_prefill_ms') is None else ms(x,'restore_ms')+ms(x,'append_prefill_ms')
 timing=dict(
  restore_ms={leg:ms(res,'restore_ms') for leg,res in (('append-s2',x),('resume-s2',y),('append-s2b',x2))},
  append_prefill_ms={leg:ms(res,'append_prefill_ms') for leg,res in (('append-s2',x),('append-s2b',x2))},
  restored_bytes={leg:ms(res,'restored_bytes') for leg,res in (('append-s2',x),('resume-s2',y),('append-s2b',x2))},
  save_seconds={cid:m['manifest']['measurements']['save_seconds'] for cid,m in manifests.items()},
  save_bytes={cid:m['manifest']['measurements']['save_bytes'] for cid,m in manifests.items()},
  save_leg_prefill_ms=sv.get('prefill_ms'),reference_prefill_ms=r.get('prefill_ms'),
  request_wall_ms={leg:1000*(res['request_end_monotonic']-res['request_start_monotonic']) for leg,res in results.items()},
  cold_vs_restore=dict(cold_prefill_ms=r.get('prefill_ms'),restore_plus_append_prefill_ms=restore_path,
   ratio=(r['prefill_ms']/restore_path) if restore_path and r.get('prefill_ms') else None,input_tokens=L,saved_prefix_tokens=N1,
   definition='cold: the one-shot reference process steps all L input tokens from a reset state (its prefill_ms, through the first generated token); restore path: the append process restores the N1-token checkpoint and steps the L-N1 remaining input tokens (restore_ms + append_prefill_ms); same binary, same input, each a fresh process with an empty expert cache'))
 return dict(passed=not problems,device_executed=False,problems=problems,gates=gates,
  comparisons=dict(save_vs_packet179=save_p179,append_vs_reference=append_cmp,chain_vs_reference=chain_cmp,append_repeat=repeat_cmp),
  reference_tokens=len(R),reference_natural_stop=len(R)<M1+M2,oracle_check=oracle_check,timing=timing,
  merged_reference_definition='reference (4) is a fresh process given NEW = P + gen[0:K] + T decoding M1+M2; (2) must equal its [0:M1], (3) its [M1:M1+M2]')

# ---------------------------------------------------------------- packet181 analyzer (v3)
# packet180's lifecycle_check above is kept byte-for-byte and is the base of lifecycle_check_v3.
QUALIFIED_BY={'scope':'one card (tp1-full512 profile) only; TP2 checkpoints not implemented; no ctxkeeper adapter yet',
 'device_gates':[{'packet':'packet179-session-swap','date':'2026-10-22','operations':['same-generation-resume']},
                 {'packet':'packet180-session-swap-v2','date':'2026-10-22','operations':['append','restore-then-save']}]}
CONTRACTS={'v1.2+p181':dict(label='qualified-one-card',packet='packet181-session-swap-v3',qualified_by=QUALIFIED_BY),
           'v1.2+p180':dict(label='experimental',packet='packet180-session-swap-v2',qualified_by=None)}
ENGINE_PREFILL_PATH='incremental'   # the engine's only prompt mechanism: one position per prompt step
APPEND_PREFILL_RATE_BOUND=1.25      # reported bound on append ms/token over cold ms/token; never a gate
NOT_CLAIMED=['one card (tp1-full512 profile) only',
 'TP2 (two-card) checkpoints are not implemented',
 'no ctxkeeper adapter yet: ctxkeeper does not call these operations',
 'model identity is host-local (stat pins); not portable across hosts',
 'no chunked/batched prefill: appended tokens and fresh prompts are both stepped one position at a time',
 'append prefill timing is an observation of fresh processes, not a performance claim']

def prefill_rows(path):
 """Per-position prompt-step rows of one native prefill-timings.jsonl as [token_index, wall_ms]."""
 rows=[]
 for line in Path(path).read_text().splitlines():
  row=json.loads(line)
  if row.get('kind')!='prefill_token':continue
  require(type(row.get('token_index')) is int and type(row.get('wall_ms')) in (int,float) and math.isfinite(row['wall_ms']),'malformed prefill row')
  rows.append([row['token_index'],float(row['wall_ms'])])
 require([i for i,_ in rows]==list(range(rows[0][0],rows[0][0]+len(rows))) if rows else True,'prefill rows are not consecutive positions')
 return rows

def append_prefill_path(result):
 """(path, source) of an append leg. packet180 receipts have no such field: their append stepped the
 same per-position prompt step, so a missing field reads as 'incremental' (legacy)."""
 rr=(result.get('checkpoint') or {}).get('restore') or {}
 if 'append_prefill_path' in rr:return rr['append_prefill_path'],'recorded'
 return ENGINE_PREFILL_PATH,'legacy: field absent (packet180 receipt), read as incremental'

def fresh_prefill_path(result):
 pf=(result.get('checkpoint') or {}).get('prefill')
 if pf is not None:return pf.get('path'),'recorded'
 return ENGINE_PREFILL_PATH,'legacy: field absent (packet180 receipt), read as incremental'

def prefill_observation(results,spec,prompt,turn,prefill=None):
 """Reported, never gated: append prefill cost per token versus the cold one-shot prefill, at the
 overall rate (brief bound x1.25) and at matched expert-cache warmth (first prompt steps of a
 fresh process in both)."""
 N1=len(prompt)+spec['K']-1;L=len(prompt)+spec['K']+len(turn)
 r=results['reference'];ms=r.get('prefill_ms')
 cold=dict(ms=ms,tokens=L,ms_per_token=ms/L if type(ms) in (int,float) and ms>0 else None,
  definition='reference process prefill_ms (all L input positions from a reset state, through the first generated token) / L')
 legs={}
 for leg in ('append-s2','append-s2b'):
  rr=(results[leg].get('checkpoint') or {}).get('restore') or {}
  ams=rr.get('append_prefill_ms');tokens=rr.get('append_prefill_tokens',L-N1)
  row=dict(ms=ams,tokens=tokens,tokens_source='recorded' if 'append_prefill_tokens' in rr else 'derived: L - N (packet180 receipt)',
   ms_per_token=ams/tokens if type(ams) in (int,float) and tokens else None)
  row['ratio_to_cold_per_token']=row['ms_per_token']/cold['ms_per_token'] if row['ms_per_token'] and cold['ms_per_token'] else None
  row['within_bound']=None if row['ratio_to_cold_per_token'] is None else row['ratio_to_cold_per_token']<=APPEND_PREFILL_RATE_BOUND
  a=(prefill or {}).get(leg);ref=(prefill or {}).get('reference')
  if a and ref:
   steps=len(a);append_ms=sum(w for _,w in a)
   first=sum(w for _,w in ref[:steps]);same=[w for i,w in ref if a[0][0]<=i<a[0][0]+steps]
   row['matched_warmth']=dict(prompt_steps=steps,append_ms=append_ms,reference_first_steps_ms=first,ratio=append_ms/first if first else None,
    definition='sum of per-position prompt-step wall_ms (prefill-timings.jsonl): the append process at positions [N, L-1) versus the reference process at its first positions [0, L-1-N); both are the first prompt steps of a fresh process with an empty expert cache')
   row['same_positions']=dict(reference_ms=sum(same),ratio=append_ms/sum(same) if same else None,
    definition='the reference process at the same positions [N, L-1), where its expert cache is already warm from positions [0, N)')
  legs[leg]=row
 return dict(gated=False,bound=APPEND_PREFILL_RATE_BOUND,cold=cold,append=legs,
  bound_definition='append_prefill_ms / append_prefill_tokens <= 1.25 x cold ms/token; reported, never a gate',
  interpretation='appended tokens and fresh prompt tokens go through the same per-position prompt step; a fresh process pays its empty expert cache on its first prompt positions, which the append spends on 127 positions and the cold reference amortizes over 469')

def lifecycle_check_v3(results,manifests,tools,spec,prompt,turn,p179_tokens,oracle,prefill=None,expect='v1.2+p181'):
 """Row b gates for packet181. Base: packet180's lifecycle_check (unchanged); its three
 'manifest identity' gates are re-evaluated for the expected contract (label, contract,
 qualified_by, engine packet). Added: the append prompt path equals the fresh reference's and the
 engine's only mechanism; for v1.2+p181 receipts, the prefill/append records. Never raises on a
 gate failure, so both streams stay in the receipt."""
 require(expect in CONTRACTS,'unknown contract '+str(expect))
 want=CONTRACTS[expect];ids=spec['checkpoint_ids']
 base=lifecycle_check(results,manifests,tools,spec,prompt,turn,p179_tokens,oracle)
 gates=dict(base['gates'])
 replaced=sorted(k for k in gates if k.startswith('manifest identity '))
 for k in replaced:gates.pop(k)
 def gate(name,ok,detail=None):gates[name]=dict(passed=bool(ok),detail=detail)
 for cid in (ids['S1'],ids['S2'],ids['S2b']):
  mm=manifests[cid]['manifest']
  ok=(mm.get('format')=='ownrt.session-checkpoint.v1' and mm.get('label')==want['label'] and mm.get('contract')==expect
      and mm.get('operations')==LIFECYCLE_OPERATIONS and mm.get('checkpoint_id')==cid
      and ('qualified_by' in mm)==(want['qualified_by'] is not None) and mm.get('qualified_by')==want['qualified_by']
      and (mm.get('engine') or {}).get('packet')==want['packet'])
  gate('manifest identity '+cid,ok,dict(label=mm.get('label'),contract=mm.get('contract'),qualified_by=mm.get('qualified_by'),
   engine_packet=(mm.get('engine') or {}).get('packet'),expected=dict(label=want['label'],contract=expect,packet=want['packet'])))
 ref_path,ref_source=fresh_prefill_path(results['reference'])
 paths=dict(reference=dict(path=ref_path,source=ref_source))
 for leg in ('append-s2','append-s2b'):
  path,source=append_prefill_path(results[leg]);paths[leg]=dict(path=path,source=source)
  gate('append prefill path '+leg,path==ref_path==ENGINE_PREFILL_PATH,dict(append=path,reference=ref_path,engine_mechanism=ENGINE_PREFILL_PATH,source=source))
 records='not evaluated: packet180 receipts predate the prefill/append record fields'
 if expect=='v1.2+p181':
  records='evaluated'
  N1=len(prompt)+spec['K']-1;L=len(prompt)+spec['K']+len(turn)
  def ck(leg):return results[leg].get('checkpoint') or {}
  for leg in ('append-s2','append-s2b'):
   c=ck(leg);rr=c.get('restore') or {};pf=c.get('prefill') or {}
   gate('append prefill record '+leg,c.get('label')==want['label'] and c.get('contract')==expect and rr.get('append_prefill_tokens')==L-N1
        and rr.get('append_prefill_path')==pf.get('path')==ENGINE_PREFILL_PATH and pf.get('first_position')==N1 and pf.get('tokens')==L-N1
        and pf.get('ms')==rr.get('append_prefill_ms')==results[leg].get('prefill_ms'),
        dict(prefill=pf,append_prefill_tokens=rr.get('append_prefill_tokens'),append_prefill_path=rr.get('append_prefill_path'),append_prefill_ms=rr.get('append_prefill_ms')))
  c=ck('reference');pf=c.get('prefill') or {}
  gate('reference prefill record',c.get('label')==want['label'] and pf.get('path')==ENGINE_PREFILL_PATH and pf.get('first_position')==0
       and pf.get('tokens')==L and pf.get('ms')==results['reference'].get('prefill_ms'),pf)
  c=ck('save-s1');pf=c.get('prefill') or {}
  gate('save prefill record',c.get('label')==want['label'] and pf.get('path')==ENGINE_PREFILL_PATH and pf.get('first_position')==0
       and pf.get('tokens')==len(prompt),pf)
  c=ck('resume-s2');pf=c.get('prefill') or {};rr=c.get('restore') or {}
  gate('resume prefill record',c.get('label')==want['label'] and pf.get('path') is None and pf.get('tokens')==0
       and rr.get('append_prefill_tokens')==0 and rr.get('append_prefill_path') is None,dict(prefill=pf,restore_path=rr.get('append_prefill_path')))
 problems=[k for k,v in gates.items() if not v['passed']]
 out=dict(base)
 out.update(passed=not problems,problems=problems,gates=gates,contract_expected=expect,label_expected=want['label'],
  qualified_by_expected=want['qualified_by'],record_gates=records,
  base_analyzer='packet180 measurement.lifecycle_check (unchanged); its three manifest identity gates are re-evaluated for the expected contract',
  replaced_base_gates=replaced,base_passed=base['passed'],base_problems=base['problems'],
  prefill_paths=paths,prefill_observation=prefill_observation(results,spec,prompt,turn,prefill),not_claimed=NOT_CLAIMED)
 return out
