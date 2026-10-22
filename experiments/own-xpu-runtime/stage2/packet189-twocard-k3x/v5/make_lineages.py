"""Packet189 lineages (v5/lineage/<name>/selection.json + dispatch-speed6.json), CPU-only, deterministic.

  v3       packet187's record selection, byte-identical (sha256 923639a9...; rank0_layers 0-25, boundary rank0,
           static snapshot; 16 keys): the record line. No packet189 row loads it; packet188 row 1 (fresh V3,
           60.50488520482965) is the fresh reference, read in place and hash-pinned by s189_decision.
  v3k      the k3 STORAGE (rank0_layers 0-26: rank 0 also holds GDN layer 26) executed as V3
           (boundary rank0: rank 0 runs 24-25, layer 26 idle on rank 0 and run by rank 1), trims off, export copy;
           the bracket LOADS this lineage: its V3 views are the in-load record-line control.
  k3x      the candidate: boundary rank0-k3 (24-26 on rank 0, rank 1 from QSA layer 27), kernel_io kernel,
           rank0_prepare async, boundary_export copy (the 20,480-byte export on the copy engine, V3's record path).
  k3trims  packet188's candidate (boundary_export kernel: the folded KioCopy export). Kept for a later attribution
           view; no packet189 device row uses it. Its behaviour is packet188's byte for byte; its selection.json gains
           the explicit boundary_export key (19 keys), so its sha256 differs from packet188's b63d9a28....
Every packet189 k3-storage selection has 19 keys (bundle 8 + V3 + kernel_io + rank0_prepare + boundary_export); the
engine refuses 18-key k3-storage selections (the export path is always named). The memory plan of the k3 storage is
packet188's derivation (storage unchanged), re-verified by the full-shape gate.
"""
import json,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parent;L=P/'lineage'
RECORD='923639a9c03fe8b58a4647ba5c4135c1f1360aaa20a1192b49c35f6fd282912e'
ROWS={'v3k':dict(boundary='rank0',kernel_io='copy',rank0_prepare='sync',boundary_export='copy'),
      'k3x':dict(boundary='rank0-k3',kernel_io='kernel',rank0_prepare='async',boundary_export='copy'),
      'k3trims':dict(boundary='rank0-k3',kernel_io='kernel',rank0_prepare='async',boundary_export='kernel')}
def main():
    sys.path.insert(0,str(P));from common import sha
    base=json.loads((L/'v3/selection.json').read_text());assert sha(L/'v3/selection.json')==RECORD,'v3 lineage must stay packet187\'s record selection'
    for name,extra in ROWS.items():
        d=L/name;d.mkdir(exist_ok=True)
        choices={}
        for k,v in base['choices'].items():
            choices[k]=v
            if k=='rank0_layers':choices[k]='0-26'
        for k in ('boundary','kernel_io','rank0_prepare','boundary_export'):choices[k]=extra[k]
        assert len(choices)==19
        (d/'selection.json').write_text(json.dumps(dict(base,choices=choices),indent=2)+'\n')
        shutil.copyfile(L/'v3/dispatch-speed6.json',d/'dispatch-speed6.json')
        if not (d/'memory-plan.json').exists():shutil.copyfile(L/'v3k/memory-plan.json',d/'memory-plan.json') # one k3 storage, one plan
        print(name,sha(d/'selection.json')[:16])
if __name__=='__main__':main()
