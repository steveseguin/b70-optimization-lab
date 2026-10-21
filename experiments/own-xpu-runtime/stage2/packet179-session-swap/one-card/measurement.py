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
