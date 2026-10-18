"""Select an already sealed view. Never run after a chain directory exists."""
import argparse,json
from compositions import P,ROOT,read,save,sha,validate,path,DIMENSIONS

def activate(selection):
 from cpu_prepare143 import verify
 verify();validate(selection)
 if (P/'build/device-cards01-p143-a').exists():raise ValueError('chain exists; selection frozen')
 from bundle_selection import FIXED,KEYS,name
 values=FIXED+tuple(selection[k] for k in DIMENSIONS);view=path(selection)
 for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json','screen-seal.json','gate.json','expected.bin.gz','actual.bin.gz'):(P/leaf).write_bytes((view/leaf).read_bytes())
 save(P/'active-composition.json',selection)
 save(P/'bundle-selection.json',dict(zip(KEYS,values),name=name(*values),placement='1',draft='draft-hc',miss='banks-batch',draft_rank=1,target_split=0,layer_boundary=24,selection_sha256=sha(view/'selection.json'),screen_seal_sha256=sha(view/'screen-seal.json')))
 from chain_seal import checked
 save(P/'build-receipt.json',checked())
 import importlib.util
 f=P.parents[1]/'ops/packet143-orchestration/submission_evidence.py';spec=importlib.util.spec_from_file_location('p143_submission_pins',f);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.pin_resealed_packet56()
 return selection
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--selection',required=True);a=ap.parse_args();activate(read(a.selection) if not a.selection.startswith('{') else json.loads(a.selection))
