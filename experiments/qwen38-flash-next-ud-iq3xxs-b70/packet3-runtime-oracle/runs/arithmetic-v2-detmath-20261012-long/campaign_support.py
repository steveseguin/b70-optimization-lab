"""Resume qualification, exact checker tests, documentation and explicit-path publication."""
import gzip,hashlib,json,os,shutil,struct,subprocess,time
from pathlib import Path

def install(m):
 H,R,I=m.HERE,m.ROOT,m.INPUTS
 def resume_test(allow_resume=False):
  proof_path=H/'resume-equality-proof.json'
  if proof_path.exists():
   proof=m.read(proof_path);m.check(proof['passed'] and proof['tokens']==8 and proof['generated_tokens_after_decode_resume']==4,'qualified resume proof');return
  bundle=R/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012/incident-retrospective'
  reference=H/'capacity-incident';label='resume-incident';d=H/('.'+label+'.partial/native')
  if not (H/label).exists():
   if not d.exists():m.launch(label,bundle,8,extra={'IQ3_CHECKPOINT_INTERVAL':'10','IQ3_STOP_AT_CHECKPOINT':'80'})
   state=m.read(d/'result.json')
   if state['status']=='failed-or-stopped':m.check(allow_resume,'explicit --resume required for interrupted qualification')
   checkpoint=m.read(d/'checkpoint.json')
   if checkpoint['next_position']<80:
    m.check(allow_resume,'explicit --resume required');m.launch(label,bundle,8,resume=True,extra={'IQ3_CHECKPOINT_INTERVAL':'10','IQ3_STOP_AT_CHECKPOINT':'80'})
    checkpoint=m.read(d/'checkpoint.json')
   if checkpoint['next_position']==80:
    m.save(H/'resume-incident-prefill-checkpoint.json',dict(**checkpoint,sha256=m.sha(d/'checkpoint.bin')))
    m.launch(label,bundle,8,resume=True,extra={'IQ3_CHECKPOINT_INTERVAL':'10','IQ3_STOP_AT_CHECKPOINT':'90'})
    checkpoint=m.read(d/'checkpoint.json')
   if checkpoint['next_position']==90 and m.read(d/'result.json')['status'] not in ('token-cap','eos'):
    state=m.read(d/'result.json');m.check(len(state['tokens'])==4 and state['tokens'][-1] not in (248044,248046),'decode checkpoint must be nonterminal')
    m.save(H/'resume-incident-decode-checkpoint.json',dict(**checkpoint,generated_tokens=4,sha256=m.sha(d/'checkpoint.bin')))
    m.launch(label,bundle,8,resume=True,extra={'IQ3_CHECKPOINT_INTERVAL':'10'})
  resumed=m.seal(label,bundle,8);a,b=m.read(resumed/'result.json'),m.read(reference/'result.json')
  m.check(len(a['tokens'])==8 and a['tokens']==b['tokens'][:8],'eight resumed tokens')
  keys=('step','token_id','top5_ids','top5_logits','logits_bf16_sha256')
  m.check(all(all(x[k]==y[k] for k in keys) for x,y in zip(a['steps'],b['steps'][:8])),'resumed logits')
  hashes={}
  for i in range(1,9):
   for p in (reference/f'step{i}').iterdir():
    name=str(p.relative_to(reference));m.check(p.read_bytes()==(resumed/name).read_bytes(),'resumed fixture '+name);hashes[name]=m.sha(p)
  m.check(len(hashes)==392,'fixture/ledger coverage')
  mid_a,_=m.mid_inventory(reference,87);mid_b,_=m.mid_inventory(resumed,87);m.check(mid_a==mid_b,'resumed mid-prompt bytes')
  proof=dict(passed=True,reference=str(reference.relative_to(R)),reference_result_sha256=m.sha(reference/'result.json'),reference_scope='First eight predictions of the uninterrupted 64-token capacity gate; not a separately run eight-token control',
   reference_generated_tokens=64,tokens=8,token_int32le_sha256=hashlib.sha256(struct.pack('<8i',*a['tokens'])).hexdigest(),raw_fixtures=384,layer_hash_ledgers=8,all_prefix_logits_and_top5_equal=True,fixture_hashes=hashes,midprompt_hashes=mid_a,
   prefill_checkpoint=m.read(H/'resume-incident-prefill-checkpoint.json'),decode_checkpoint=m.read(H/'resume-incident-decode-checkpoint.json'),context=4096,interrupted_in_prefill_and_decode=True,generated_tokens_after_decode_resume=4,
   uninterrupted_receipt_sha256=m.sha(reference/'receipt.json'),resumed_receipt_sha256=m.sha(resumed/'receipt.json'))
  m.save(proof_path,proof);m.save(H/'status.json',dict(status='resume-gate-passed',updated_utc=m.utc()))

 def checker_tests(label):
  checker=m.module('long_checker_tests',H/'suite_check.py');oracle=H/label
  manifest=m.read(I/'suite-manifest.json');entry=next(e for e in manifest['prompts'] if e['prompt_id']==label)
  checks=[]
  m.check(checker.check_prompt(oracle,oracle,entry)==(len(m.read(oracle/'result.json')['tokens']),48*min(8,len(m.read(oracle/'result.json')['tokens']))),'self checker')
  checks.append(dict(test='oracle self comparison',passed=True))
  scratch=H/'.checker.partial';m.disk_guard();scratch.mkdir(exist_ok=True);copy=scratch/label
  # Copy only exactness inputs; verbose logs and teardown have no role in corruption tests.
  copy.mkdir()
  for name in ('result.json','input.json','receipt.json','validation.json'):shutil.copyfile(oracle/name,copy/name)
  for p in oracle.glob('step*'):shutil.copytree(p,copy/p.name)
  shutil.copytree(oracle/'midprompt',copy/'midprompt')
  def corrupt(name,path,edit):
   raw=path.read_bytes();path.write_bytes(edit(raw))
   try:checker.check_prompt(copy,oracle,entry)
   except (ValueError,OSError,KeyError,TypeError) as e:checks.append(dict(test=name,passed=True,rejection=str(e)))
   else:raise RuntimeError('checker accepted '+name)
   finally:path.write_bytes(raw)
  corrupt('tail token',copy/'result.json',lambda raw:json.dumps({**json.loads(raw),'tokens':json.loads(raw)['tokens'][:-1]+[json.loads(raw)['tokens'][-1]^1]}).encode())
  corrupt('generation stream byte',copy/('step'+str(min(8,len(m.read(oracle/'result.json')['tokens']))))/'layer-47.bf16',lambda b:bytes([b[0]^1])+b[1:])
  pos=entry['midprompt_positions'][-1];folder=copy/'midprompt'/str(pos)
  corrupt('mid-prompt selection byte',folder/'layer-03.ids.i32',lambda b:bytes([b[0]^1])+b[1:])
  corrupt('mid-prompt layer47 byte',folder/'layer-47.bf16',lambda b:bytes([b[0]^1])+b[1:])
  corrupt('mid-prompt truncated selection',folder/'layer-03.ids.i32',lambda b:b[:-4])
  hidden=copy/'hidden-midprompt';folder.rename(hidden)
  try:
   try:checker.check_prompt(copy,oracle,entry)
   except (ValueError,OSError,KeyError,TypeError) as e:checks.append(dict(test='missing mid-prompt position',passed=True,rejection=str(e)))
   else:raise RuntimeError('checker accepted missing position')
  finally:hidden.rename(folder)
  shutil.rmtree(copy);scratch.rmdir()
  path=H/'checker-tests.json';all_checks=m.read(path) if path.exists() else {};all_checks[label]=checks;m.save(path,all_checks)

 def count_prior(r):return 1+count_prior(r['prior_attempt']) if r.get('prior_attempt') else 0
 def elapsed(r,key):return r.get(key,0)+(elapsed(r['prior_attempt'],key) if r.get('prior_attempt') else 0)
 def refresh():
  prompts=m.read(I/'prompts.json');entries=[]
  for row in prompts['prompts']:
   label=row['id'];d=H/label;bundle=I/label
   if not (d/'receipt.json').exists():continue
   r,result,v=m.read(d/'receipt.json'),m.read(d/'result.json'),m.read(d/'validation.json')
   m.check(r['verified'],'verified run')
   positions=m.rows(d/'positions.jsonl');bins=[]
   for lo,hi in ((0,100),(100,256),(256,512),(512,1024),(1024,1536),(1536,2048),(2048,2300),(2300,4096)):
    vals=[p['seconds'] for p in positions if lo<=p['position']<hi]
    if vals:bins.append(dict(first_position=lo,last_position=min(hi-1,len(positions)-1),positions=len(vals),mean_seconds_per_position=sum(vals)/len(vals)))
   entries.append(dict(prompt_id=label,prompt_tokens=r['prompt_tokens'],input_bundle=str(bundle.relative_to(R)),input_bundle_hashes={n:m.sha(bundle/n) for n in ('tokens.txt','input.json','identity.tsv','plan.tsv','vocab.bin')},
    oracle_directory=str(d.relative_to(R)),oracle_receipt_sha256=m.sha(d/'receipt.json'),generated_tokens=len(result['tokens']),first_8_token_ids=result['tokens'][:8],last_8_token_ids=result['tokens'][-8:],ended_early=len(result['tokens'])<32,termination=result['status'],context=4096,
    fixture_steps=list(range(1,min(8,len(result['tokens']))+1)),midprompt_positions=[r['position'] for r in v['selection_summary']],selection_summary=v['selection_summary'],mean_seconds_per_position=r['mean_seconds_per_position'],elapsed_seconds=elapsed(r,'elapsed_seconds'),cpu_seconds=elapsed(r,'cpu_seconds'),cpu_accounting_complete=m.timing_complete(r),position_timing_bins=bins,site_cost_bins=m.read(d/'site-cost-summary.json')['bins'] if (d/'site-cost-summary.json').exists() else [],prompt_source=row,execution_segments=1+count_prior(r)))
  manifest=dict(schema='own-runtime.iq3.suite-inputs.v1',arithmetic='iq3-p17-detmath-v2',context=4096,token_cap=32,suite_sha256=prompts['corpus_sha256'],prompts_manifest_sha256=m.sha(I/'prompts.json'),complete=len(entries)==2,prompts=entries,total_elapsed_seconds=sum(e['elapsed_seconds'] for e in entries),total_cpu_hours=sum(e['cpu_seconds'] for e in entries)/3600,cpu_accounting_complete=all(e['cpu_accounting_complete'] for e in entries))
  m.save(I/'suite-manifest.json',manifest)
  table='| Prompt | Prompt tokens | Generated | End | Processes | First 8 IDs | Last 8 IDs | Seconds/position | CPU hours |\n| --- | ---: | ---: | --- | ---: | --- | --- | ---: | ---: |\n'
  for e in entries:table+=f"| {e['prompt_id']} | {e['prompt_tokens']} | {e['generated_tokens']} | {e['termination']} | {e['execution_segments']} | {', '.join(map(str,e['first_8_token_ids']))} | {', '.join(map(str,e['last_8_token_ids']))} | {e['mean_seconds_per_position']:.4f} | {e['cpu_seconds']/3600:.4f} |\n"
  timing='| Prompt | Zero-based positions | Mean seconds/position |\n| --- | --- | ---: |\n'
  for e in entries:
   for b in e['position_timing_bins']:timing+=f"| {e['prompt_id']} | {b['first_position']}–{b['last_position']} | {b['mean_seconds_per_position']:.4f} |\n"
  qsa='| Prompt | Zero-based positions | Pool s/position | Select s/position | Attention s/position | All sites s/position |\n| --- | --- | ---: | ---: | ---: | ---: |\n'
  for e in entries:
   for b in e['site_cost_bins']:qsa+=f"| {e['prompt_id']} | {b['first_position']}–{b['last_position']} | {b['qsa_pool_seconds']:.4f} | {b['qsa_select_seconds']:.4f} | {b['qsa_attention_seconds']:.4f} | {b['site_seconds']:.4f} |\n"
  selections='| Prompt | Position (zero-based) | Consumed tokens | Admitted | Dropped | Layers with score ties | Cutoff tie layers |\n| --- | ---: | ---: | ---: | ---: | ---: | --- |\n'
  for e in entries:
   for s in e['selection_summary']:selections+=f"| {e['prompt_id']} | {s['position']} | {s['prompt_ordinal']} | {s['admitted']} | {s['dropped']} | {s['layers_with_ties']}/12 | {s['cutoff_tie_layers']} |\n"
  capacity='PASS' if (H/'capacity-incident/equality-proof.json').exists() else 'PENDING'
  resume='PASS' if (H/'resume-equality-proof.json').exists() else 'PENDING'
  text=f'''# Long-context arithmetic-v2 CPU oracles

Completed and verified: {len(entries)}/2. Arithmetic `iq3-p17-detmath-v2` for the separate
Unsloth UD-IQ3_XXS quantized compressed model; context capacity 4,096, 32 generated tokens.
EOG 248044 or 248046 is retained and then stops generation. No device was accessed.

{table}
Numerical-process wall time including resume segments: {manifest['total_elapsed_seconds']:.3f} seconds.
Measured user + system time: {manifest['total_cpu_hours']:.6f} CPU hours.
CPU/wall accounting complete for every segment: **{manifest['cpu_accounting_complete']}**.
If false after recovering a crashed supervisor, totals cover only saved timing receipts;
missing time remains unknown. Numerical state and bytes are verified independently.
These are CPU oracle costs, not serving speeds. Per-position times include the original
streaming weight loader and per-site logging; selected capture positions also include
the selection audit. Checkpoint write/verification is outside those position timings. Receipt totals include
every segment, including each fresh initialization and state restoration; position bins
use the accepted forward passes, while receipts retain any discarded interrupted work.
Token 1 includes initialization and prefill. `positions.jsonl`, `tokens.jsonl`, and
`result.json` retain timings, every token, top-five logits, logit hashes and decoded text.

{timing}
{qsa}
QSA recomputes all complete four-token pools and scores them at every position.
Attention reduces the selected positions in score order, at most 2,048 plus up to
three trailing positions. Its cost grows through the budget edge; pool scoring
continues to grow after it. The frozen CPU allocator also scans its growing allocation
history. The long runs therefore use preregistered 100-position segments, carrying
the exact saved state into a fresh process after each segment. This bounds bookkeeping
and separates it from long-context attention cost. No model history is reset. Every
segment runs once; a failed segment stops the campaign without automatic retry.
Wall-time growth still cannot be attributed solely to QSA. The retained site
logs allow that distinction to be examined; no faster arithmetic was substituted.

One host allocation adaptation was required: the sealed adapter's 256 MiB temporary
pool would overflow near 1,225 admitted positions. `scratch-capacity.patch` enlarges
both its backing allocation and its pool bound to 512 MiB, without changing any
arithmetic. The initial short replay was stopped cleanly before the long runs; its
partial evidence is retained in `preparation-stopped-capacity/`. Both equality gates
use the final enlarged-pool build. A second short preparation replay stopped to add
an immediate disk check before the final teardown write. The completed capacity gate
was then preserved while receipt compression was finalized. These preparation stops
do not count as a numerical failure or as long-context oracle coverage. The original numerical sources remain read-only;
`build-receipt.json` binds the two-constant overlay and generated include relocation.

Capacity proof: **{capacity}**. Capacity changes allocated cache extents and bounds only;
valid-position arithmetic and the frozen 4,096-position RoPE table stay unchanged.
See `capacity-analysis.md` and the 4,096-capacity `capacity-incident/equality-proof.json`:
64 sealed tokens, all logit hashes/top-five records, 384 BF16 fixtures and eight layer
ledgers must match before LONG-A starts. LONG-A must be sealed before LONG-B starts.
Both gates compare against the unchanged sealed arithmetic, with no tolerance.

Resume proof: **{resume}**. The original suite wrapper could not resume; `oracle_long.cpp`
adds a checkpoint of **all** plan buffers, position, token history, generated IDs,
logit records and log offsets every 100 completed positions. Each buffer is hashed,
the temporary checkpoint is fully reread, then atomically renamed. Resume validates
input/plan/admission/capacity binding and every buffer, truncates output logs to the
checkpoint, and discards only this attempt's fixtures beyond that point. No weights
are checkpointed. The incident diagnostic compares the first eight predictions of the uninterrupted
64-token capacity gate with a run interrupted in prefill (after 80 positions) and
generation (after 90): eight tokens, 384 fixtures, eight ledgers, logit records and
all mid-prompt records. Four tokens must be generated after the second restoration.
The earlier six-token diagnostic ended naturally after three tokens and therefore
proved only prefill restoration; its narrow evidence is retained separately. LONG-A
was stopped during initial prefill until the stronger gate passed.
See `resume-equality-proof.json`. Failed runs never retry automatically; use `--resume`
explicitly. Recovery first archives active logs against their old position endpoint,
before state rollback. Completed partials also finalize log retention; a lost supervisor
timing receipt is marked incomplete instead of silently counting it as zero.
Completed runs are verified and skipped. Status updates after every position.

Prompts use distinct source files, once each, from the tracked corpus's **prose** class:
LONG-A is 598 rendered tokens from `docs/current-reproducibility-map.md`; LONG-B is
2,271 from `docs/model-effort-index.md`. Exact historical source bytes were recovered
by the corpus's hashes and matched back to its concatenated text; current files have
changed. The prompts are document prefixes, cut at a word boundary without padding or
repetition, preceded by “Summarize the following document in about 200 words.”
`prompts.json` in the input directory records source commits, hashes, offsets and
counts. The frozen publisher Jinja template, thinking disabled, no system message,
and packet2 tokenizer are identical to the suite; all twelve old renderings replay.

`prepare_long.py` calls the unchanged packet29 `prepare(out,prompt)` for the five-file
runtime bundles: `tokens.txt`, `input.json`, `identity.tsv`, `plan.tsv`, `vocab.bin`.
Those files have no short-prompt or context 256/1024 limit. Old runtime **CLI wrappers**
do have bounds; packet44 owns extending them. Python window `--input` takes the bundle
directory; the native runtime takes `tokens.txt`. `suite-manifest.json` uses the suite
schema with token_cap 32 and context 4096, plus explicit mid-prompt positions.

Positions in `midprompt/<position>/` are **zero-based**, including the five requested
indices 2040, 2048, 2049, 2100 and the last prompt index. Extra 2047, 2050 and 2051
records make the exact boundary clear. `prompt_ordinal` is the one-based consumed
count. Each directory retains the twelve QSA layers' full 2,051-slot int32 little-endian
selection buffers (unused slots are -1), ordered admitted IDs, full FP32 pool-score bits,
stable-tie counts and the 20,480-byte layer-47 BF16 stream. Scores are audited using
unchanged Core::dot and detmath::sqrt, without altering model buffers.

{selections}
The budget is 512 complete pools × 4 tokens, plus an incomplete trailing pool. Thus
zero-based 2048 and 2049 may still admit every token; first dropped positions appear
at zero-based 2051 (2,052 consumed tokens). Ties keep the lower pool index first.
`cutoff_tie_layers` identifies ties affecting which complete pools are admitted.

Generation fixture layout is unchanged: step1 is the final prompt position;
steps 1–8 each contain 48 `[1,4,2560]` BF16 little-endian streams and a hash ledger.
The suite checker is reused and extended to compare all tokens, those fixtures,
and every mid-prompt selection/stream byte. Device outputs must provide the same
midprompt directory and binary names; pool-score audit JSON is oracle evidence, not
a required device output. Self-comparison and corrupted token, fixture, selection,
stream, truncated-list and missing-position copies are tested in `checker-tests.json`.
This is long-context arithmetic coverage, not a performance or full quality claim.

All commands use nice 19 and idle I/O. Two OpenMP threads per numerical process;
sequential campaign, no more than two oracle processes and eight compute threads.
Original affinity 4–15,20–31 is preserved. Combined oracle anonymous memory is
checked below 11.5 GB; no device access, sudo, mlock or host setting changes.
`df -B1 /` runs before builds/checkpoints/compression and every ten seconds; below
8 GB stops work. Scratch stays below 2 GB. Site logs rotate at checkpoints, compress
losslessly with restored-hash verification, and retain raw/compressed hashes in
`log-retention.json`. Large log and teardown artifacts are necessary execution
receipts; completed long-run teardown is losslessly compressed with a raw-hash receipt
in `teardown-retention.json`, and earlier segment teardowns in `resume-archives.json`; restore `.gz` with gzip and verify that manifest's raw SHA256. Checkpoints
are removed only after complete validation, with their hash and regeneration recipe
retained. No executable, weights or generated cache is committed.

Reproduction, from repository root (all writes stay in the two new directories):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/vllm-xpu/bin/python -B {H.relative_to(R)}/prepare_long.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 -B {H.relative_to(R)}/build_cpu.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B {H.relative_to(R)}/long_run.py --stage capacity
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B {H.relative_to(R)}/long_run.py --stage resume-test
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B {H.relative_to(R)}/long_run.py --stage long --publish
nice -n 19 ionice -c 3 python3 -B {H.relative_to(R)}/suite_check.py {H.relative_to(R)}
```

Long runs use private systemd user units with the same affinity, nice/IO settings,
SIGTERM forwarding and SendSIGKILL=no. Each verified run is atomically renamed,
committed with explicit paths and the requested coauthor, fetched/merged if needed,
and pushed to main. No branch, stash, rebase or unrelated file edits.
'''
  for root in (H,I):
   links='\nFinal records: [closeout]('+os.path.relpath(H/'closeout.md',root)+'), [receipt audit]('+os.path.relpath(H/'final-audit.json',root)+'), [recovery tests]('+os.path.relpath(H/'recovery-tests.json',root)+').\n'
   content=text+links
   tmp=root/'README.md.tmp';tmp.write_text(content);m.check(tmp.read_text()==content,'README readback');tmp.replace(root/'README.md')
  # Consumer convenience: a tiny CPU-only forwarder; authoritative checker stays with evidence.
  wrapper='''"""Run the exact long-oracle checker; standard library only."""
import runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
runpy.run_path(str(ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/suite_check.py'),run_name='__main__')
'''
  (I/'suite_check.py').write_text(wrapper)

 def publish(label):
  def git(*args):return subprocess.check_output(m.PREFIX+['git','-c','pack.threads=1','-c','index.threads=1','-c','gc.auto=0',*args],cwd=R,text=True,stderr=subprocess.STDOUT)
  m.check(git('branch','--show-current').strip()=='main','main only')
  # Explicit two-directory pathspec. Ignore rules exclude all scratch/build/live state.
  paths=[str(H.relative_to(R)),str(I.relative_to(R))]
  git('add','--',*paths);git('diff','--cached','--check','--',*paths)
  if git('diff','--cached','--name-only','--',*paths).strip():
   print(git('commit','-m','Add verified long-context arithmetic-v2 CPU oracle: '+label,'-m','Co-Authored-By: Codex <noreply@openai.com>','--',*paths),flush=True)
  git('fetch','origin','main')
  if subprocess.call(m.PREFIX+['git','merge-base','--is-ancestor','origin/main','HEAD'],cwd=R)!=0:
   print(git('diff','--stat','HEAD...origin/main'),flush=True)
   print(git('merge','--no-edit','-m','Merge origin/main for long CPU oracle receipts\n\nCo-Authored-By: Codex <noreply@openai.com>','origin/main'),flush=True)
  print(git('push','origin','HEAD:main'),flush=True)
 m.resume_test=resume_test;m.checker_tests=checker_tests;m.refresh=refresh;m.publish=publish
