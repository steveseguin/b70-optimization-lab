"""Current validated native receipt planning; historical reference plan remains unchanged."""
from pathlib import Path
import hashlib,importlib.util,json,struct,sys
HERE=Path(__file__).resolve().parent
GATE=HERE.parent.parent/'dedicated-gate'
assert GATE.is_dir() and (GATE/'colocated_control.py').is_file()
sys.path.insert(0,str(GATE))
import reference_one_row as R
C,BASE=R.C,R.BASE
REGISTRATION=HERE/'build-registration.json'

def make_plan(config):
 config=Path(config).resolve();cfg=json.loads(config.read_text());identity=json.loads(R.IDENTITY.read_text());tokens=json.loads(R.INPUT.read_text())['tokens']
 BASE.require(BASE.digest(R.INPUT)==identity['input_json_sha256'] and len(tokens)==244,'saved exact244 prefix')
 BASE.require(hashlib.sha256(struct.pack('<244i',*tokens)).hexdigest()==identity['prefix_le_i32_sha256'],'packed prefix')
 BASE.require(cfg['boundaries']==[0,23,48] and cfg['context']==4096 and cfg['max_new']==1 and cfg['prompt_tokens']==tokens,'fixed target-only geometry/input')
 BASE.require(cfg.get('live_draft') is False and cfg.get('use_proposals') is False,'no draft/proposals')
 receipt=json.loads(Path(cfg['build_receipt']).read_text())
 registration_path=Path(cfg.get('build_registration',str(REGISTRATION))).resolve()
 BASE.require(registration_path.parent==HERE and registration_path.name.startswith('build-registration') and registration_path.suffix=='.json','local explicit registration record')
 registration=json.loads(registration_path.read_text());CURRENT=registration['binary_sha256']
 BASE.require(BASE.digest(cfg['build_receipt'])==registration['receipt_sha256'],'registered exact build receipt')
 BASE.require(type(cfg.get('reference_tie_diagnostic')) is bool,'explicit diagnostic ON/OFF')
 BASE.require(receipt['binary_sha256']==CURRENT,'explicit pinned router tie candidate')
 # SAME existing planning authority used by colocated_control, but target-only base path.
 # This validates binary SHA and EVERY current compiled source against receipt; no stale pins bypassed.
 p=C.base.make_plan(config)
 out=Path(p['output'])
 for stage in p['stages']:
  rank=stage['id'];argv=C.native_argv(stage['argv'],out,rank)
  argv=BASE.replace_options(argv,{'--context':4096,'--max-new':1,'--retain-steps':1},{'--draft-rank'})
  BASE.require(not any(x.startswith(('--draft','--oracle','--provider','--pipeline')) for x in argv),'no residual draft/pipeline/oracle flags')
  BASE.require(BASE.option(argv,'--target-split')=='23' and BASE.option(argv,'--activations')=='f32','same original target arithmetic modes')
  stage['argv']=argv;stage['native_output']=str(out/f'native/rank{rank}')
  BASE.require(not any(k in stage['environment']for k in ['OWNRT_ROUTER_TIE_DIAGNOSTIC','OWNRT_LOOKUP_VIEW','OWNRT_L4_RAW_HISTORY','OWNRT_L4_PREP_HISTORY']),'no inherited diagnostic flags')
  if cfg['reference_tie_diagnostic']:stage['environment']['OWNRT_ROUTER_TIE_DIAGNOSTIC']='1'
 p.update(schema='ownrt.current-reference-one-row-plan.v1',binary_sha256=CURRENT,reference_tie_diagnostic=cfg['reference_tie_diagnostic'],
    speculative_depth=1,native_launch_max_new=1,native_request_max_new=1,eos_token_ids=[],
    mode='target-only-none',live_draft=False,use_proposals=False,diagnostic_only=True,speed_claim=False,
    execution_ready=True,old_reference_binary_sha256=identity['current_binary_sha256'],
    binary_identity_changed=True,limits='General reference tie-order diagnostic target-only244/1 at4096/F32/cut23. Historical df2c observation is a separate binary identity; no runtime oracle or quality claim.')
 spec=importlib.util.spec_from_file_location('router_adapter_plan_deps',C.ADAPTER);adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
 for path in (Path(__file__).resolve(),Path(R.__file__).resolve(),Path(C.__file__).resolve(),R.INPUT,R.IDENTITY,registration_path,Path(cfg['build_receipt']),Path(adapter.PARENT),Path(adapter.ENV_SOURCE),C.ADAPTER):p['pins'][str(path)]=BASE.digest(path)
 for name,digest in adapter.source_pins().items():
  path=Path(name) if Path(name).is_absolute() else adapter.ROOT/name
  BASE.require(BASE.digest(path)==digest,'adapter dependency identity');p['pins'][str(path)]=digest
 return p
