"""Offline BMG-G31 instruction counts for production vs candidate kernels (CPU-only; packet81's pipeline).

icpx -fsycl-device-only (record device flags) -> llvm-link with the SYCL device libraries -> sycl-post-link ->
llvm-spirv -> /usr/bin/ocloc (bmg-g31, -ze-fp32-correctly-rounded-divide-sqrt) with IGC_ShaderDumpEnable. The
finalizer assembly of every kernel in the TU is kept (evidence/isa/*.asm.gz). Counting method (same asm text the
study's opcode histogram used):
  static        = //.instCount of the kernel; opcode histogram over non-comment, non-label lines;
  K loop        = the largest backward branch region (label before a backward `jmpi`/`while`/`goto`);
  dynamic walk  = a single-lane walk through the loop body: predicated `goto`/`jmpi` fall through (variant
                  'fallthrough') or are taken (variant 'taken'); an unpredicated structured `goto JIP UIP`
                  continues at UIP; unpredicated `(W) jmpi` follows its target unless it is a backward edge;
                  `join` counts as executed; the normal path is the 'fallthrough' variant (IGC laid out the finite-scale
                  arm as the fallthrough block in production and in every candidate; the walked float-mul count is
                  reported as the consistency check: 2 per weight on the normal IQ2 path, 3 on the exceptional one).
  per weight    = normal-path walk / weights per lane per loop iteration (gate/up 64 = 8 chains x 8,
                  down 128 = 16 chains x 8 per 256-step; the last down step is a 2.5-step tail).
A candidate is kept for the window only if its normal-path dynamic count per weight is below production's
AND it has no spill metadata, scratch messages or register-indirect address fills from private memory.
Writes evidence/isa.json. Not a device measurement; no speed claim.
"""
import gzip,hashlib,json,os,re,resource,shlex,subprocess,sys,time
from collections import Counter
from pathlib import Path
from build_engine import P,ROOT,NATIVE,BUILD,EV,limits,sha,rel,units_idle
sys.path.insert(0,str(P.parents[1]/'ops'));from compile_turn import turn
ICPX=Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx');TOOLS=ICPX.parent/'compiler';LIB=ICPX.parent.parent/'lib'
INC=['-I'+str(NATIVE/'checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x'),'-I'+str(NATIVE/'root'),'-I'+str(P)]
FLAGS=['-fsycl','-fsycl-device-only','-O2','-std=gnu++20','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
LIBS=[LIB/('libsycl-'+n+'.bc') for n in ('crt','complex','complex-fp64','cmath','cmath-fp64','imf','imf-fp64','imf-bf16','fallback-cstring','fallback-complex','fallback-complex-fp64','fallback-cmath','fallback-cmath-fp64','fallback-imf','fallback-imf-fp64','fallback-imf-bf16','itt-user-wrappers','itt-compiler-wrappers','itt-stubs','native-bfloat16')]
KERNELS={'production-gateup':('p90exp','gateup',64,640,'p90exp::Kernel<IQ2_S,2560,WG64,false,true>'),'production-down':('p1006KernelILj2EE','down',128,320,'p100::Kernel<2>'),
         'exp-diet':('p193diet6GateUp6submit','gateup',64,640,'p193diet::GateUp'),'exp-act-epilogue':('p193diet9GateUpAct','gateup',64,640,'p193diet::GateUpAct'),
         'down-diet':('p193diet4Down','down',128,320,'p193diet::Down'),'production-act':('p193diet13ActProduction','act',1,1,'p193diet::ActProduction (expsact twin)')}
LABEL=re.compile(r'^(_0_\d+|L\d+):');OPC=re.compile(r'^(?:\((?:W&)?~?f\d\.\d\)|\(W\))?\s*([a-z][a-z0-9_.]*)')
def instructions(lines):
 """(index, text, label or None, opcode or None) for every non-comment line."""
 rows=[]
 for i,l in enumerate(lines):
  s=l.strip()
  if not s or s.startswith('//'):continue
  m=LABEL.match(s)
  if m:rows.append((i,s,m.group(1),None));continue
  op=OPC.match(s);rows.append((i,s,None,op.group(1) if op else None))
 return rows
def branch(text):
 """(kind, predicated, targets) for goto/jmpi/while, else None."""
 s=text.strip();pred=s.startswith('(')
 body=s[s.index(')')+1:].strip() if pred and ')' in s else s
 m=re.match(r'(goto|jmpi|while|break|cont)\b.*?((?:_0_\d+|L\d+)(?:\s+(?:_0_\d+|L\d+))?)\s*(?://|$)',body)
 if not m:return None
 return m.group(1),pred and not s.startswith('(W)'),m.group(2).split()
def analyze(text,weights_per_iteration,weights_per_lane):
 lines=text.splitlines();rows=instructions(lines);labels={lab:n for n,(i,s,lab,op) in enumerate(rows) if lab}
 ops=Counter(op for i,s,lab,op in rows if op);loads=[s for i,s,lab,op in rows if op and op.startswith('load.')]
 # largest backward region
 loop=None
 for n,(i,s,lab,op) in enumerate(rows):
  b=branch(s) if op in ('goto','jmpi','while') else None
  if not b:continue
  for t in b[2]:
   if t in labels and labels[t]<n and (loop is None or n-labels[t]>loop[1]-loop[0]):loop=(labels[t],n)
 def walk(start,end,take):
  n=start;count=0;guard=0;seen=set()
  while n<=end and guard<200000:
   guard+=1;i,s,lab,op=rows[n]
   if lab or not op:n+=1;continue
   b=branch(s) if op in ('goto','jmpi','while') else None
   count+=1
   if b:
    kind,pred,targets=b
    if kind=='while':break
    if pred:
     if take and targets and targets[0] in labels and labels[targets[0]]>n:n=labels[targets[0]];continue
     n+=1;continue
    target=targets[-1] if kind=='goto' else targets[0]
    if target in labels and labels[target]>n:n=labels[target];continue
    if target in labels and labels[target]<=n:
     if n==end:break
     n+=1;continue   # inner backward edge (data-dependent loop): one iteration
   n+=1
  return count
 out=dict(static_instructions=None,opcodes=dict(ops.most_common()),static_loads=len(loads),load_kinds=dict(Counter(l.split()[0] if not l.startswith('(') else l.split()[1] for l in loads).most_common()))
 m=re.search(r'//\.instCount (\d+)',text);out['static_instructions']=int(m[1]) if m else len([1 for r in rows if r[3]])
 g=re.search(r'numGRF=(\d+)',text);out['configured_grf']=int(g[1]) if g else None
 head=lines[:60];out['spill_metadata']=[l for l in head if l.startswith('//.spill')]
 out['scratch_messages']=[s for i,s,lab,op in rows if op and any(x in s.lower() for x in ('scratch','spill','fill'))]
 out['register_indirect']=sum(1 for i,s,lab,op in rows if op and 'r[a0' in s);out['slm_messages']=sum(1 for i,s,lab,op in rows if op and ('.slm' in s));out['barriers']=sum(1 for i,s,lab,op in rows if op and ('barrier' in s or 'sync.bar' in s or op=='sync'))
 if loop and sum(1 for r in rows[loop[0]:loop[1]+1] if r[3])>=200:
  s_,e_=loop;body=rows[s_:e_+1]
  bops=Counter(op for i,s,lab,op in body if op);out['loop']=dict(found=True,label=rows[s_][2],body_lines=e_-s_,static_body_instructions=sum(1 for r in body if r[3]),
   goto=bops.get('goto',0),join=bops.get('join',0),body_opcodes=dict(bops.most_common(12)),loads=sum(1 for r in body if r[3] and r[3].startswith('load.')))
  ft=walk(s_,e_,False);tk=walk(s_,e_,True)
  def fmul(take):
   n=s_;count=0;guard=0
   while n<=e_ and guard<200000:
    guard+=1;i,s,lab,op=rows[n]
    if lab or not op:n+=1;continue
    b=branch(s) if op in ('goto','jmpi','while') else None
    if op=='mul' and ':f' in s:count+=1
    if b:
     kind,pred,targets=b
     if kind=='while':break
     if pred:
      if take and targets and targets[0] in labels and labels[targets[0]]>n:n=labels[targets[0]];continue
      n+=1;continue
     target=targets[-1] if kind=='goto' else targets[0]
     if target in labels and labels[target]>n:n=labels[target];continue
     if target in labels and labels[target]<=n:
      if n==e_:break
      n+=1;continue
    n+=1
   return count
  out['loop'].update(walk_fallthrough=ft,walk_taken=tk)
  normal=ft;out['loop'].update(normal_path_dynamic=normal,normal_path_variant='fallthrough',walked_float_muls=fmul(False),weights_per_iteration=weights_per_iteration,dynamic_per_weight=normal/weights_per_iteration,static_body_per_weight=out['loop']['static_body_instructions']/weights_per_iteration)
 else:
  out['loop']=dict(found=False,note='no K loop (unrolled); whole-kernel single-lane walk normalised by weights per lane')
  ft=walk(0,len(rows)-1,False);tk=walk(0,len(rows)-1,True);normal=ft
  out['whole_kernel_walk']=dict(fallthrough=ft,taken=tk,normal_path_dynamic=normal,weights_per_lane=weights_per_lane,dynamic_per_weight=normal/weights_per_lane if weights_per_lane>1 else None)
 return out
def main():
 limits();out=BUILD/'isa';out.mkdir(exist_ok=True);(EV/'isa').mkdir(exist_ok=True);units=units_idle()
 src=P/'micro.cpp';cmds=[[str(ICPX),*FLAGS,*INC,'-MMD','-MF',str(out/'dependencies.d'),'-c',str(src),'-o',str(out/'kernels.bc')],
  [str(TOOLS/'llvm-link'),'-only-needed',str(out/'kernels.bc'),*map(str,LIBS),'--suppress-warnings','-o',str(out/'linked.bc')],
  [str(TOOLS/'sycl-post-link'),'-O2','-spec-const=emulation','-emit-only-kernels-as-entry-points','-ir-output-only',str(out/'linked.bc'),'-o',str(out/'image.bc')],
  [str(TOOLS/'llvm-spirv'),'--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers,-SPV_KHR_fma',str(out/'image.bc'),'-o',str(out/'kernels.spv')],
  ['/usr/bin/ocloc','compile','-spirv_input','-file',str(out/'kernels.spv'),'-device','bmg-g31','-options','-ze-fp32-correctly-rounded-divide-sqrt','-out_dir',str(out/'aot')]]
 env={**os.environ,'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(out/'igc'),'IGC_ShowFullVectorsInShaderDumps':'1'}
 for p in (out/'igc').glob('*') if (out/'igc').exists() else []:p.unlink()
 t=time.monotonic()
 with turn():
  for i,cmd in enumerate(cmds):
   with (EV/'isa'/f'stage-{i}.log').open('w') as log:subprocess.run(['nice','-n','19',*cmd],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,check=True,timeout=900)
 kernels={}
 for p in sorted((out/'igc').glob('*entry_*.asm')):
  data=p.read_text();name=data.splitlines()[0]
  for key,(needle,cls,wpi,wpl,pretty) in KERNELS.items():
   if needle in name and key not in kernels:
    if key=='exp-diet' and 'GateUpAct' in name:continue
    art=EV/'isa'/(key+'.asm.gz');art.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    kernels[key]=dict(kernel=pretty,entry=name,kind=cls,assembly=rel(art),sha256=sha(art),**analyze(data,wpi,wpl))
 assert set(kernels)==set(KERNELS),'kernels missing from the dump: '+str(set(KERNELS)-set(kernels))
 prod={'gateup':kernels['production-gateup'],'down':kernels['production-down']}
 decisions={}
 def per_weight(k):return k['loop']['dynamic_per_weight'] if k['loop'].get('found') else k['whole_kernel_walk']['dynamic_per_weight']
 for key in ('exp-diet','exp-act-epilogue','down-diet'):
  k=kernels[key];p_=prod[k['kind']];reasons=[]
  if k['loop'].get('found')!=p_['loop'].get('found'):reasons.append('loop structure differs from production (candidate loop found=%s, production=%s)'%(k['loop'].get('found'),p_['loop'].get('found')))
  cw,pw=per_weight(k),per_weight(p_)
  if cw>=pw:reasons.append(f"no dynamic reduction: {cw:.2f} >= {pw:.2f} per weight")
  if k['spill_metadata'] or k['scratch_messages']:reasons.append('spills/scratch: '+str((k['spill_metadata'][:2],k['scratch_messages'][:2])))
  decisions[key]=dict(kept=not reasons,reasons=reasons,candidate_dynamic_per_weight=cw,production_dynamic_per_weight=pw,ratio=cw/pw,
   static=k['static_instructions'],production_static=p_['static_instructions'],grf=k['configured_grf'],method='K-loop walk' if k['loop'].get('found') else 'whole-kernel walk')
 deps={}
 d=out/'dependencies.d'
 if d.exists():deps={rel(Path(n).resolve()):sha(n) for n in shlex.split(d.read_text().replace('\\\n',' ').split(':',1)[1]) if n and Path(n).resolve().is_relative_to(ROOT)}
 (EV/'isa.json').write_text(json.dumps(dict(schema='packet193.isa.v1',passed=True,device_executed=False,scope='Offline BMG-G31 finalizer assembly (ocloc + IGC dump); static counts and a single-lane walk estimate; never a device timing',
  method=__doc__,commands=cmds,seconds=round(time.monotonic()-t,1),source_sha256=sha(src),sources=deps,device_libraries=[f.name for f in LIBS],device_libraries_digest=hashlib.sha256(''.join(sha(f) for f in LIBS).encode()).hexdigest(),kernels=kernels,decisions=decisions,units=units,
  max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=1)+'\n')
 for key,k in kernels.items():
  L=k['loop'];W=k.get('whole_kernel_walk',{});print(key,'static',k['static_instructions'],'grf',k['configured_grf'],'loop',L.get('found'),'body',L.get('static_body_instructions'),'walk ft/tk',L.get('walk_fallthrough',W.get('fallthrough')),L.get('walk_taken',W.get('taken')),'per-weight',round((L.get('dynamic_per_weight') or W.get('dynamic_per_weight') or 0),2),'goto/join',L.get('goto'),L.get('join'),'spill',bool(k['spill_metadata'] or k['scratch_messages']),'indirect',k['register_indirect'],'slm',k['slm_messages'])
 print(json.dumps(decisions,indent=1))
if __name__=='__main__':main()
