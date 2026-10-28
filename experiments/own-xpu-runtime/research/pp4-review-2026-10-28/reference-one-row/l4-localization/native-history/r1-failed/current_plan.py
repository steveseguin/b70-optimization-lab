"""Current validated native receipt planning; historical reference plan remains unchanged."""
from pathlib import Path
import hashlib,importlib.util,json,struct,sys
HERE=Path(__file__).resolve().parent
GATE=HERE.parents[2]/'dedicated-gate'
assert GATE.is_dir() and (GATE/'colocated_control.py').is_file()
sys.path.insert(0,str(GATE))
import reference_one_row as R
C,BASE=R.C,R.BASE
CURRENT='4601f8d3720b47092c68de7ade54de06deb13620a2b3abe0fb6aa5aa6115692f'

def make_plan(config):
 config=Path(config).resolve();cfg=json.loads(config.read_text());identity=json.loads(R.IDENTITY.read_text());tokens=json.loads(R.INPUT.read_text())['tokens']
 BASE.require(BASE.digest(R.INPUT)==identity['input_json_sha256'] and len(tokens)==244,'saved exact244 prefix')
 BASE.require(hashlib.sha256(struct.pack('<244i',*tokens)).hexdigest()==identity['prefix_le_i32_sha256'],'packed prefix')
 BASE.require(cfg['boundaries']==[0,23,48] and cfg['context']==4096 and cfg['max_new']==1 and cfg['prompt_tokens']==tokens,'fixed target-only geometry/input')
 BASE.require(cfg.get('live_draft') is False and cfg.get('use_proposals') is False,'no draft/proposals')
 receipt=json.loads(Path(cfg['build_receipt']).read_text())
 BASE.require(receipt['binary_sha256']==CURRENT,'explicit pinned L4 history build')
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
 p.update(schema='ownrt.current-reference-one-row-plan.v1',binary_sha256=CURRENT,
    speculative_depth=1,native_launch_max_new=1,native_request_max_new=1,eos_token_ids=[],
    mode='target-only-none',live_draft=False,use_proposals=False,diagnostic_only=True,speed_claim=False,
    execution_ready=True,old_reference_binary_sha256=identity['current_binary_sha256'],
    binary_identity_changed=True,limits='New L4-history target-only244/1 at4096/F32/cut23. Historical df2c observation is a separate binary identity; no runtime oracle or quality claim.')
 spec=importlib.util.spec_from_file_location('router_adapter_plan_deps',C.ADAPTER);adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
 for path in (Path(__file__).resolve(),Path(R.__file__).resolve(),Path(C.__file__).resolve(),R.INPUT,R.IDENTITY,Path(cfg['build_receipt']),Path(adapter.PARENT),Path(adapter.ENV_SOURCE),C.ADAPTER):p['pins'][str(path)]=BASE.digest(path)
 for name,digest in adapter.source_pins().items():
  path=Path(name) if Path(name).is_absolute() else adapter.ROOT/name
  BASE.require(BASE.digest(path)==digest,'adapter dependency identity');p['pins'][str(path)]=digest
 return p
