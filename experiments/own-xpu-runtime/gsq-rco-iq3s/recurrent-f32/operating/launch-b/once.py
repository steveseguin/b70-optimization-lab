#!/usr/bin/env python3
"""Separately admitted F32-B pair with initial-only extra cache headroom."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,shutil
P=Path(__file__).resolve().parent;PARENT=P.parent/'once.py'
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-recurrent-f32-b.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b');UNIT='gsq-recurrent-f32-b.service'
EXTRA_INITIAL_CACHE=128<<20
ROOT_INITIAL_REQUIRED=27_000_000_000+(256<<20)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,s):
 if not v:raise RuntimeError(s)
for f,h in json.loads((P/'parent-pins.json').read_text()).items():require(sha(f)==h,'frozen A source '+f)
s=importlib.util.spec_from_file_location('rf32_frozen_a_once',PARENT);BASE=importlib.util.module_from_spec(s);s.loader.exec_module(BASE)
S=BASE.S;O=BASE.O;M=BASE.M
BASE.CONTROL=O.CONTROL=M.CONTROL=CONTROL
BASE.EVIDENCE=O.EVIDENCE=M.EVIDENCE=EVIDENCE
BASE.UNIT=O.UNIT=M.UNIT=UNIT
PARENT_TRANSPORT=S.A.Transport
class InitialMarginTransport(PARENT_TRANSPORT):
 def __init__(self,*args,**kwargs):
  # Exactly once before the pair's first owner is constructed. The inherited
  # ongoing guard continues to reserve27GB+128MiB; it gets no extra stage0 charge.
  require(shutil.disk_usage(M.R).free>=ROOT_INITIAL_REQUIRED,'initial F32-B driver-cache headroom')
  super().__init__(*args,**kwargs)
S.A.Transport=InitialMarginTransport

def review():
 f=P/'evidence/independent-review.json';r=json.loads(f.read_text());require(r['passed'],'independent B source review')
 for name,h in r['source_sha256'].items():require(sha(Path(name) if Path(name).is_absolute() else M.R/name)==h,'B reviewed source drift')
 return f

def build_plan():
 reviewed=review();p=BASE.build_plan()
 p.update(schema='gsq.recurrent-f32.once-b.v1',initial_cache_growth_margin_bytes=EXTRA_INITIAL_CACHE,initial_root_free_required_bytes=ROOT_INITIAL_REQUIRED,initial_margin_scope='Once immediately before Transport construction; ongoing27GB+128MiB reserve and all capture stages unchanged',previous_attempt='A failed storage guard; no success qualification or automatic retry')
 p['source_sha256'].update({str(f):sha(f) for f in [Path(__file__),P/'parent-pins.json',P/'source-preparation.json',reviewed]})
 p['monitor_configuration']['initial_transport_cache_margin_bytes']=EXTRA_INITIAL_CACHE
 return p
O.build_plan=build_plan
if __name__=='__main__':
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2))
 else:raise SystemExit(O.run(a.run))
