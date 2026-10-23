"""Packet194 lineages (v5/lineage/<name>/selection.json + dispatch-speed6.json + memory-plan.json), CPU-only, deterministic.

  v3          packet187's record selection, byte-identical (sha256 923639a9...; 0-25 storage; 16 keys): the record line
              of packet186/187. CPU gates only (production-shape identity with packet189).
  v3k         packet189's V3 views of the k3 storage (19 keys, sha256 92f5fcf7...): CPU gates only (identity with packet189).
  k3x-record  packet189's k3x selection byte for byte (19 keys, sha256 c5443bbf...): THE RECORD SELECTION (packet190
              chain 62.345282). It has no `expert_gateup` key: the engine treats an absent key as `production`. CPU gates
              prove this 19-key load is the record path on the new engine (captures, census and canonical transcript
              identical to packet189's). No packet194 device row loads it (a 19-key load cannot switch to a 20-key view).
  k3x         the bracket's CONTROL: k3x-record + `expert_gateup production` (20 keys). Same storage, same execution
              flags, the record gate/up kernel; the CPU gates prove its captures equal k3x-record's (= packet189's).
  k3x-diet    the CANDIDATE: k3x + `expert_gateup diet` (20 keys): packet193's exact gate/up instruction diet
              (p193diet::GateUp) at every exp-halfcache gate/up site; nothing else differs.
Every packet194 k3-storage view selection has 20 keys; the 19-key record selection stays loadable. The memory plan of
the k3 storage is packet188/189's derivation (storage unchanged; the diet adds no allocation), re-verified by the
full-shape gate.
"""
import json,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parent;L=P/'lineage'
RECORD='923639a9c03fe8b58a4647ba5c4135c1f1360aaa20a1192b49c35f6fd282912e'
K3X_RECORD='c5443bbfbc88b39fd562956a55ce05667de0781f640fd0cd522a1e5800f392bb'
V3K='92f5fcf7373a47c40ca156aa5bd86a3f9e973744bc45c51e8735005ef9712ae3'
K3={'boundary':'rank0-k3','kernel_io':'kernel','rank0_prepare':'async','boundary_export':'copy'}
ROWS={'k3x':'production','k3x-diet':'diet'}
def main():
    sys.path.insert(0,str(P));from common import sha
    base=json.loads((L/'v3/selection.json').read_text());assert sha(L/'v3/selection.json')==RECORD,'v3 lineage must stay packet187\'s record selection'
    assert sha(L/'v3k/selection.json')==V3K,'v3k lineage must stay packet189\'s'
    assert sha(L/'k3x-record/selection.json')==K3X_RECORD,'k3x-record must stay packet189\'s k3x selection (the record selection)'
    for name,gateup in ROWS.items():
        d=L/name;d.mkdir(exist_ok=True)
        choices={}
        for k,v in base['choices'].items():
            choices[k]=v
            if k=='rank0_layers':choices[k]='0-26'
        for k,v in K3.items():choices[k]=v
        choices['expert_gateup']=gateup
        assert len(choices)==20
        (d/'selection.json').write_text(json.dumps(dict(base,choices=choices),indent=2)+'\n')
        shutil.copyfile(L/'v3/dispatch-speed6.json',d/'dispatch-speed6.json')
        shutil.copyfile(L/'k3x-record/memory-plan.json',d/'memory-plan.json') # one k3 storage, one plan (packet188/189's)
        print(name,sha(d/'selection.json')[:16])
    # k3x (20 keys) differs from k3x-record (19 keys) by exactly the explicit production key
    a=json.loads((L/'k3x-record/selection.json').read_text());b=json.loads((L/'k3x/selection.json').read_text())
    assert dict(b['choices'],**{})=={**a['choices'],'expert_gateup':'production'} and a['draft']==b['draft']
    c=json.loads((L/'k3x-diet/selection.json').read_text());assert c['choices']=={**b['choices'],'expert_gateup':'diet'} and c['draft']==b['draft']
if __name__=='__main__':main()
