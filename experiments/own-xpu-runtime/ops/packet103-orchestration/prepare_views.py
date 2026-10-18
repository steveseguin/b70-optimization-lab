"""Seal only required views after the exhaustive 512-composition CPU gate."""
import json
import orchestrate as o
from bundle_selection import KEYS,views
from seal_inputs import prepare as prepare_inputs, seal_view
from composite_jobs import variants
from read_screens import collect,require_current

def main():
 o.limits()
 prepare_inputs()
 screens=collect();control,candidate,confirmed=o.select(screens)
 config=o.composition(screens,control,candidate,confirmed,{}, {})
 choices={'control':control,'candidate':candidate,**variants(config,True)}
 # Seal the measured largest allocation and every optional dimension.
 choices['all-dimensions']=dict(zip(KEYS,list(views().values())[-1]))
 report=json.loads((o.P/'evidence/full-shape.json').read_text())
 largest=max(report['runs'],key=lambda r:r['postload_device_bytes'])
 choices['largest-allocation']=dict(zip(KEYS,views()[largest['view']]))
 sealed={}
 for label,choice in choices.items():
  view=seal_view(tuple(choice[k] for k in KEYS),'1')
  sealed[label]=dict(path=o.pin_path(view),sha256=o.sha(view/'screen-seal.json'))
 require_current(screens)
 decision=o.freeze_decision(config,screens)
 o.save(o.P/'composition-selection.json',config)
 o.save(o.O/'screens-current.json',screens)
 o.save(o.O/'view-preparation.json',dict(passed=True,device_executed=False,
   supported_and_cpu_checked_compositions=len(views()),sealed=sealed,
   decision=o.pin_path(decision),decision_sha256=o.sha(decision),
   scope='Required immutable view manifests only; every supported composition has the full CPU gate. Additional views can be sealed without compiling.'))
 print(json.dumps(dict(decision=str(decision),sealed_views=len(sealed),device_executed=False)))
if __name__=='__main__':main()
