"""Packet188 lineages (v5/lineage/<name>/selection.json + dispatch-speed6.json), CPU-only, deterministic.

  v3       packet187's record selection, byte-identical (sha256 923639a9...; rank0_layers 0-25, boundary rank0,
           static snapshot; 16 keys): the fresh V3 control row (the record line).
  v3k      the k3 STORAGE (rank0_layers 0-26: rank 0 also holds GDN layer 26) executed as V3
           (boundary rank0: rank 0 runs 24-25, layer 26 idle on rank 0 and run by rank 1), trims off;
           the bracket LOADS this lineage: its V3 views are the in-load record-line control.
  k3trims  the same storage with boundary rank0-k3 (24-26 on rank 0, rank 1 from QSA layer 27), kernel_io kernel,
           rank0_prepare async: the candidate (smoke row and bracket views).
  k3, k3kio, k3prep
           the candidate with neither / only kernel_io / only rank0_prepare (attribution selections: CPU gates
           exercise every combination; no device row uses them).
Every packet188 storage selection has 18 keys (bundle 8 + V3 + kernel_io + rank0_prepare). The memory plan of the
k3 storage is derived by the full-shape gate from the v3 plan plus the measured census delta.
"""
import json,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parent;L=P/'lineage'
RECORD='923639a9c03fe8b58a4647ba5c4135c1f1360aaa20a1192b49c35f6fd282912e'
ROWS={'v3k':dict(boundary='rank0',kernel_io='copy',rank0_prepare='sync'),
      'k3trims':dict(boundary='rank0-k3',kernel_io='kernel',rank0_prepare='async'),
      'k3':dict(boundary='rank0-k3',kernel_io='copy',rank0_prepare='sync'),
      'k3kio':dict(boundary='rank0-k3',kernel_io='kernel',rank0_prepare='sync'),
      'k3prep':dict(boundary='rank0-k3',kernel_io='copy',rank0_prepare='async')}
def main():
    sys.path.insert(0,str(P));from common import sha
    base=json.loads((L/'v3/selection.json').read_text());assert sha(L/'v3/selection.json')==RECORD,'v3 lineage must stay packet187\'s record selection'
    for name,extra in ROWS.items():
        d=L/name;d.mkdir(exist_ok=True)
        choices={}
        for k,v in base['choices'].items():
            choices[k]=v
            if k=='rank0_layers':choices[k]='0-26'
        choices['boundary']=extra['boundary'];choices['kernel_io']=extra['kernel_io'];choices['rank0_prepare']=extra['rank0_prepare']
        assert len(choices)==18
        (d/'selection.json').write_text(json.dumps(dict(base,choices=choices),indent=2)+'\n')
        shutil.copyfile(L/'v3/dispatch-speed6.json',d/'dispatch-speed6.json')
        print(name,sha(d/'selection.json')[:16])
if __name__=='__main__':main()
