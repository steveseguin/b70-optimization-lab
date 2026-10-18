#!/usr/bin/env python3
"""Mechanical full-file delta inventories against both immutable merge parents."""
import hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
PARENTS={'40':('50d9e00311a6bc8dcb43297f9d02ac7285e6e788','packet40-suite'),
         '44':('421a4ab5029680c2f88c78c7c7fdb4a05d6fc6c4','packet44-context')}
SELF={'INTEGRATE.md','merge-inventory.json'}
def main():
 from storage import admit
 admit(20_000_000,build_extra=0)
 current={}
 for path in sorted(P.rglob('*')):
  if not path.is_file() or 'build' in path.relative_to(P).parts or '__pycache__' in path.parts:continue
  name=str(path.relative_to(P))
  if name in SELF:continue
  raw=path.read_bytes();current[name]={'sha256':hashlib.sha256(raw).hexdigest(),
   'git_blob':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'bytes':len(raw)}
 inventories={};tables=[]
 for packet,(commit,directory) in PARENTS.items():
  base=str(P.parent.relative_to(ROOT)/directory)+'/'
  raw=subprocess.check_output(['nice','-n','19','ionice','-c','3','git','ls-tree','-r',commit,'--',base],cwd=ROOT,text=True)
  before={line.split('\t',1)[1][len(base):]:line.split('\t',1)[0].split()[2] for line in raw.splitlines()}
  rows=[]
  for name in sorted(set(before)|set(current)|SELF):
   old=before.get(name);new=current.get(name)
   status='generated_inventory' if name in SELF else 'omitted_historical_artifact' if new is None else 'added' if old is None else 'unchanged' if old==new['git_blob'] else 'modified'
   rows.append(dict(path=name,status=status,parent_git_blob=old,current=new))
  inventories[packet]=dict(commit=commit,path=base,files=rows)
  changed=[r for r in rows if r['status']!='unchanged']
  tables.append('## Every file difference against packet'+packet+'\n\nParent `'+commit+'`. Full blob IDs and current SHA256 values are in `merge-inventory.json`. “Omitted” means a historical receipt/doc/source was not copied into the new packet; the parent file remains untouched.\n\n| Path | Disposition |\n|---|---|\n'+''.join('| `'+r['path']+'` | '+r['status']+' |\n' for r in changed))
 receipt=dict(schema='packet45.merge-inventory.v1',parents=inventories,
  generated_inventory_exclusions=sorted(SELF),scope='every non-build packet file; parent files remain unchanged; self inventories list names without self hashes')
 (P/'merge-inventory.json').write_text(json.dumps(receipt,indent=2)+'\n')
 intro="""# Packet45 mechanical integration

Start with packet44-context at `421a4ab50`; layer packet40-suite at `50d9e0031`
over that copy using both parents' INTEGRATE inventories, then the measured
packet42/39 kernels and rank0 draft protocol. No parent tree was modified.
`merge-start.json` also pins both kernel input trees and 52 source/measurement
files to their immutable Git commit, tree/blob IDs and SHA256 values.

## Merge inventory by behavior

- From 40: configurable fixture retention, 128-token cap and 99-interval submission
  metric, selected-kernel draft with non-blocking readback, cancellation of a
  wrong half before each compute launch, strict rollback and speed companions.
- From 44: allocation capacities 256/4096/32768, bounded 32-position launch buckets,
  full 16-bit caches, long 32-token manifest/oracle binding, context-aware wrappers,
  K2 representative lengths, arithmetic identity v2 and precisely linked math.
- New: p42 route/packed-gate/tiny/GDN registered candidates; p39 plan fusions
  physically remove launches; K2 fresh integrated-chain timing and 3% threshold
  above 2 ms/token; rank0 draft with a duplicate head and 22/26 split; reverse final
  streams before rank1 head; rank1 placement remains selectable at 24/24; complete
  memory ledger including strict rollback image; final CPU gate/seal scripts.

## Conflicts and resolutions

Capacity behavior always wins. main.cpp retains packet44 context admission and packet40’s 128-token cap;
mtp.hpp keeps packet44 cache/bounded QSA geometry with packet40 asynchronous draft and new head ownership;
rank.hpp retains packet40 cancellation/snapshot with packet44 extents and the new reverse handoff;
window.py/draft_window.py/suite.py keep packet44 context/long32 binding plus packet40 retention,
metrics and selected-dispatch draft reference. build.py seals the merged tree,
not either parent's historical passes. kernel-submissions.json is regenerated.
Conflicting wrapper tests were updated to the merged contracts. Legacy seal.py
and seal_context.py remain historical helper code; build.py routes to seal45.py.

The copied p42 cooperative pool used capacity/4 for its append group. Packet44
launches only newly completed pools plus one append group, so the 136-token CPU
case skipped the append. Merely replacing capacity with launch_extent also failed.
The merged kernel uses append_pools(s) and maps each pool relative to pos/4.
This conflict was caught by the actual
K1 capacity fixture and recorded in capacity-fixture-gates.json.

The independent review also required accepting a target hit before issuing the
next rank0 draft, snapshotting before context admission, and restoring both
prepared-command banks on terminal rollback. Memory review added the previously
omitted strict snapshot and corrected actual head-sharing telemetry.

The next merge must retain both allocation placements, frozen arithmetic,
full-state rollback, registry/fusion compatibility and manifest-derived caps.
Run the CPU reproduction steps and a new coordinator chain; never carry forward
a passed boolean from a different source or binary. Packet42 dense.fourparts is
excluded; its actual expanded-row stride defect is documented in KERNELS.md.

"""
 (P/'INTEGRATE.md').write_text(intro+'\n'.join(tables))
 print(json.dumps({p:{'files':len(v['files']),'changed':sum(r['status']!='unchanged' for r in v['files'])} for p,v in inventories.items()}))
if __name__=='__main__':main()
