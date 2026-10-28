"""Narrow storage-mode experiment using the unchanged guarded dedicated driver."""
import argparse,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
TOOLS=HERE.parents[2]/'engine/tools'
assert (TOOLS/'dedicated_provider_driver.py').is_file()
sys.path.insert(0,str(TOOLS))
import dedicated_provider_driver as D

def make_plan(config):
 cfg=json.loads(Path(config).read_text());mode=cfg.get('lookup_storage')
 D.base.require(mode in ('copy','view'),'explicit lookup storage mode')
 p=D.make_plan(config)
 D.base.require(p.get('dedicated_bulk_prefill') is True and p.get('dedicated_prefill_pipeline') is True,'registered dedicated bulk pipeline')
 for owner in p['stages']+[p['provider']]:
  D.base.require('OWNRT_LOOKUP_VIEW'not in owner['environment'],'storage mode must come from pinned experiment config')
 D.base.require(p['stages'][0]['first'] and p['stages'][0]['environment'].get('OWNRT_LOOKUP_COPY')!='0','first-target copy control required')
 if mode=='view':p['stages'][0]['environment']['OWNRT_LOOKUP_VIEW']='1'
 p['host_lookup_storage']=mode;p['pins'][str(Path(__file__).resolve())]=D.base.digest(__file__)
 return p

def main():
 a=argparse.ArgumentParser();a.add_argument('--config',type=Path);a.add_argument('--plan',type=Path,required=True);a.add_argument('--run',action='store_true');a.add_argument('--admission',type=Path);a.add_argument('--unit');x=a.parse_args()
 if not x.run:
  D.base.save(x.plan,make_plan(x.config));print(json.dumps(dict(plan=str(x.plan),sha256=D.base.digest(x.plan),device_execution_requested=False)));return
 p=json.loads(x.plan.read_text());D.base.require(p==make_plan(p['config']),'exact storage plan/source pins')
 D.base.require(x.admission is not None and x.unit,'explicit admission and unit');ad=json.loads(x.admission.read_text());D.base.require(ad['plan_sha256']==D.base.digest(x.plan),'plan admission hash')
 r=D.lifecycle.execute(p,ad,x.unit);print(json.dumps({k:r[k]for k in ('passed','error','returncodes','wall_seconds','lifecycle_phases')}))
if __name__=='__main__':main()
