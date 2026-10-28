#!/usr/bin/env python3
"""Execute registered full-engine AOT argv; never executes resulting engine.
Parent authorization required. Distinct research manifest/runner pins are truthful.
"""
import concurrent.futures as cf
import hashlib,json,os,pathlib,shlex,subprocess,time
HERE=pathlib.Path(__file__).resolve().parent
ENGINE=HERE.parents[2]/'engine';SRC=ENGINE/'src'
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=1)+'\n')
def build():
 recipe=HERE/'full-build-command-plan.json';manifest=HERE/'full-build-manifest-research-copy.json'
 plan=json.loads(recipe.read_text());basepath=pathlib.Path(plan['base_receipt']);base=json.loads(basepath.read_text())
 need(sha(basepath)==plan['base_receipt_sha256'] and base['binary_sha256']==plan['base_binary_sha256'],'registered base receipt')
 need(sha(base['binary'])==base['binary_sha256'],'actual b732 base binary')
 need(sha(ENGINE/'build-manifest.json')==base['build_manifest_sha256'],'unchanged canonical manifest')
 for n,h in base['sources'].items():need(sha(SRC/n)==h,'native source drift '+n)
 for n,h in base['runtime_assets'].items():need(sha(n)==h,'runtime asset drift')
 out=pathlib.Path(plan['target_out']);oldout=str(pathlib.Path(base['binary']).parent)
 for name,cmd in plan['commands'].items():
  expected=[]
  for arg in base['commands'][name]['cmd']:
   expected.append(arg.replace(oldout,str(out)))
   if arg=='-fsycl':expected.append('-fsycl-targets=intel_gpu_bmg_g31')
  need(cmd==expected,'only exact AOT flag treatment, argv/link ordering '+name)
 out.mkdir(exist_ok=False);(out/'tmp').mkdir();(out/'logs').mkdir()
 env=dict(os.environ,TMPDIR=str(out/'tmp'))
 record={'status':'building','recipe_sha256':sha(recipe),'research_manifest_sha256':sha(manifest),
  'runner_sha256':sha(__file__),'base_receipt_sha256':sha(basepath),'base_binary_sha256':base['binary_sha256'],
  'jobs':4,'cpu_affinity':sorted(os.sched_getaffinity(0)),'nice':os.getpriority(os.PRIO_PROCESS,0),
  'only_treatment':'-fsycl-targets=intel_gpu_bmg_g31 added after -fsycl at every compile and link',
  'commands':{}}
 need(record['nice']==19 and set(record['cpu_affinity'])<=set(range(8,16)),'required bounded CPU policy')
 save(out/'research-build.json',record)
 def invoke(item):
  name,cmd=item;start=time.monotonic();run=subprocess.run(cmd,env=env,capture_output=True,text=True)
  (out/'logs'/(name+'.stdout')).write_text(run.stdout);(out/'logs'/(name+'.stderr')).write_text(run.stderr)
  return name,dict(cmd=cmd,rc=run.returncode,seconds=round(time.monotonic()-start,3),stderr=run.stderr[-6000:])
 units=[(n,c) for n,c in plan['commands'].items() if n!='link']
 try:
  with cf.ThreadPoolExecutor(max_workers=4) as pool:
   for name,result in pool.map(invoke,units):
    record['commands'][name]=result;save(out/'research-build.json',record);print(name,'rc',result['rc'],result['seconds'],'s',flush=True)
  need(all(v['rc']==0 for v in record['commands'].values()),'compile failure (full logs retained)')
  name,result=invoke(('link',plan['commands']['link']));record['commands'][name]=result;save(out/'research-build.json',record)
  need(result['rc']==0,'AOT link failed (full logs retained)')
  deps=set()
  for name,_ in units:
   tokens=shlex.split((out/pathlib.Path(name).with_suffix('.d')).read_text().replace('\\\n',' '))
   for token in tokens[1:]:
    p=pathlib.Path(token).absolute()
    if p.is_relative_to(SRC):deps.add(str(p.relative_to(SRC)))
  need(deps==set(base['sources']),'actual dependency source inventory differs from registered base')
  sources={n:sha(SRC/n) for n in sorted(deps)};need(sources==base['sources'],'native source drift during build')
  need(all(sha(n)==h for n,h in base['runtime_assets'].items()),'runtime asset drift during build')
  binary=out/pathlib.Path(base['binary']).name
  receipt=dict(schema='ownrt.engine.build.v1',binary=str(binary),binary_sha256=sha(binary),
   objects={name:sha(out/name) for name,_ in units},sources=sources,commands=record['commands'],
   runtime_assets=base['runtime_assets'],generated_authority=base['generated_authority'],
   generated_dependencies=base['generated_dependencies'],build_script_sha256=sha(__file__),build_manifest_sha256=sha(manifest),
   research_build=dict(recipe=str(recipe),recipe_sha256=sha(recipe),manifest=str(manifest),
     base_receipt=str(basepath),base_receipt_sha256=sha(basepath),canonical_build_script_executed=False,
     canonical_build_manifest_sha256=sha(ENGINE/'build-manifest.json'),treatment=record['only_treatment']))
  save(out/'build-receipt.json',receipt);record['status']='passed';record['binary_sha256']=receipt['binary_sha256'];save(out/'research-build.json',record)
  print('binary',receipt['binary_sha256'],flush=True)
 except BaseException as e:
  record['status']='failed';record['error']=repr(e);save(out/'research-build.json',record);raise
if __name__=='__main__':build()
