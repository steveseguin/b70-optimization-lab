"""Apply the request-order-only change and its reporting/identity checks."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
def once(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b,1)
for name in ('one-card','two-card'):
    p=P/name
    f=p/'worker.py';s=f.read_text()
    s=once(s,"result=[dict(prompt_id='prefill512',prompt_tokens=512)] + manifest['prompts']", "# The first registered prompt is the distinct warm-up, run ONCE.\n result=[manifest['prompts'][0],dict(prompt_id='prefill512',prompt_tokens=512),*manifest['prompts'][1:]]")
    s=once(s,' return result\n',' require(len({tuple(e[\'tokens\']) for e in result})==13,\'all prompts must be distinct; no warm-up reuse\')\n return result\n')
    s=once(s,'def record_request(dest,entry,result):','def record_request(dest,entry,result,observed):')
    s=once(s," result.update(prompt_id=entry['prompt_id'],oracle_check=check)",""" result.update(prompt_id=entry['prompt_id'],oracle_check=check)
 if entry['prompt_id']=='prefill512':
  warm_id=measurement.IDS[0]
  require(list(observed)==[warm_id],'prefill must be second, after exactly one distinct request')
  warm=read(observed[warm_id]['path'])
  warm_tokens=entries()[0]['tokens']
  require(warm_tokens!=entry['tokens'] and warm.get('cached_tokens')==0,'distinct uncached warm-up required')
  require(warm['request_end_monotonic']<=result['request_start_monotonic'],'warm-up must finish before prefill')
  result['warmup']=dict(prompt_id=warm_id,prompt_token_sha256=measurement.digest(warm_tokens),
    receipt_sha256=sha(Path(observed[warm_id]['path'])),output_tokens=len(warm['tokens']),
    completed_before_prefill=True,request_count_before_prefill=1,suite_prompt_used_once=True,
    state_reset_before_prefill=True,cached_tokens=0)
""")
    s=s.replace('record_request(dest,entry,result)','record_request(dest,entry,result,observed)')
    s=once(s," save(a.output/'report-inputs.json',dict(passed=True,requests=rows[1:],prefill=rows[0],", " by_id={r['prompt_id']:r for r in rows}\n save(a.output/'report-inputs.json',dict(passed=True,requests=[by_id[i] for i in measurement.IDS],prefill=by_id['prefill512'],execution_order=[e['prompt_id'] for e in items],")
    f.write_text(s)
    f=p/'measurement.py';s=f.read_text()
    s=s.replace("schema='packet163.full-gate.v1'","schema='packet165.warm-prefill.v1'")
    start=s.index("  metrics['prefill']=dict(")
    end=s.index('\n return metrics',start)
    s=s[:start]+'''  # Primary prefill rate is request TTFT based, not an invented device duration.
  ttft_ms=1000*(result['timing_rows'][0]['completed_monotonic']-result['request_start_monotonic'])
  require(math.isfinite(ttft_ms) and ttft_ms>0,'positive request TTFT required')
  warm=result.get('warmup')
  if warm is not None:
   require(warm.get('prompt_id')==IDS[0] and warm.get('prompt_token_sha256')!=digest(prompt_tokens),'warm-up identity')
   require(warm.get('completed_before_prefill')is True and warm.get('state_reset_before_prefill')is True and warm.get('cached_tokens')==0 and warm.get('request_count_before_prefill')==1,'warm-up/reset evidence')
  metrics['prefill']=dict(input_tokens=512,users=1,elapsed_ms=ttft_ms,tok_s=512000/ttft_ms,
    timing_definition='512 / request TTFT seconds: request_start_monotonic through first generated-token completed_monotonic; excludes model load and reset; includes controller/host and first-token work; not HTTP TTFT',
    native_prompt_loop_ms=ms,native_prompt_loop_tok_s=512000/ms,
    native_prompt_loop_definition='native prompt-loop wall time through first generated token, including final prompt position and output head; not device-only time',
    prefill_phase_device_ms=None,prefill_phase_device_status='not available: unchanged token-timing build does not expose an isolated device prefill phase',
    construction='first 512 tokenizer IDs from one unrepeated real-document excerpt, no special tokens',cached_tokens=0,oracle_covered=False,
    warmup=warm,measurement_temperature='warm-runtime/cold-prompt' if warm else 'cold-first-request or legacy evidence; not packet165 warm proof')
''' +s[end:]
    f.write_text(s)
    f=p/'screen.py';s=f.read_text()
    s=once(s," if result.get('strict512'):\n", " if result.get('strict512'):\n  require(proof.get('prefill',{}).get('prefill',{}).get('warmup') is not None,'warm prefill proof required')\n")
    s=once(s,"prefill=dict(users=1,cached_tokens=0)","prefill=dict(users=1,cached_tokens=0,request_index=1,warmup_prompt=measurement.IDS[0],suite_prompt_used_once=True)")
    f.write_text(s)
    f=p/'cpu_seal.py';s=f.read_text()
    s=once(s,' return pins'," native=read(HERE/'inherited-native.json')\n from common import ROOT\n for name,expected in native['embedded_readonly_dependencies'].items():\n  require(sha(ROOT/name)==expected,'frozen embedded native dependency changed: '+name)\n return pins")
    f.write_text(s)
    identity=json.loads((p/'identity.json').read_text())
    identity.update(measurement_protocol='packet165: first suite prompt once, full reset, prefill512, remaining suite once',native_binary_unchanged_from_packet163=True)
    (p/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
print('Request order, warm/reset proof and TTFT definition adapted; native binaries unchanged.')
