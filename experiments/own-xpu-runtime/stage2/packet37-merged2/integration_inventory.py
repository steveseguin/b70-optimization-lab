#!/usr/bin/env python3
"""Refresh packet37's reviewable file inventory against immutable packet32 files."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'packet32-pipeline'
REASONS={
'CMakeLists.txt':'Link prepared-host and packet33 translation units with strict compile/link precision flags.',
'adapter.cpp':'Prepare the selected packet33 QSA dispatch path with unchanged non-GEMV bindings.',
'adapter_fixture.cpp':'Use measured packet29 non-GEMV incumbents in K2.',
'argument_block.hpp':'Guard pointer-only bounded launch blocks for prepared submissions.',
'backend.hpp':'Add capture/replay support and prepared command representation.',
'dispatch.hpp':'Admit packet33 QSA implementation identifier 3.',
'dispatch_registry.hpp':'Extend the closed C++ dispatch vocabulary with five packet33 kernels.',
'dispatch-incumbent.json':'Copy the measured packet29 map solely as K2 incumbent provenance.',
'fixture_driver.cpp':'Gate linked packet33 QSA under K1 and time it under K2.',
'gemv_timing.cpp':'Gate/time packet33 GEMVs and same-run packet29 controls, retaining R5 alternatives.',
'k2-class-registry.json':'Declare complete candidates, workloads and packet29 incumbent identities.',
'k2_incumbents.hpp':'Compile the registered packet29 controls into native fixtures.',
'k2_summary.py':'Port measured fusion selection; compare both HC sites and emit rank dispatch maps.',
'kernel-registry.json':'Extend the machine-readable closed kernel vocabulary.',
'main.cpp':'Prepare/replay both rank parities, residency and per-token host receipts.',
'owner.cpp':'Capture stable launches, preserve lifetime rules, and remove redundant dependencies.',
'owner.hpp':'Own prepared command state and validated allocation/event lifetimes.',
'owner_api.hpp':'Expose prepared backend operations through the owner API.',
'pipeline.py':'Carry packet37 rank preparation and per-token receipts through the Python controller.',
'rank.hpp':'Bind prepared submissions to speculation parity and rollback transaction state.',
'real_campaign.py':'Run inherited real-model oracle modes through packet37 binaries.',
'single_device.cpp':'Replay prepared device operations without per-launch discovery or binding work.',
'submission_overlay.py':'Maintain the precision/dependency overlay used by the build.',
'validation_mirror.py':'Mirror new registry entries in CPU validation contracts.',
'window.py':'Prepare packet37 windows, provenance binding, deadlines and fault-safe ownership.',
'source-packet32.json':'Record the source packet identity; copied historical receipts remain inherited evidence.',
'integration_inventory.py':'Regenerate this explicit file-by-file merge inventory.',
}
def reason(name):
 if name in REASONS:return REASONS[name]
 if name.startswith('p33'):return 'Extend and gate existing packet33 arithmetic, shape specialization or binding entry points.'
 if name.startswith(('prepared_','resident_')):return 'Qualify prepared launch equivalence, allocation-free replay or lookup residency.'
 if name.startswith(('review','test_')) or name.endswith(('_test.cpp','_gate.py','-tests.json','-gates.json')):return 'Record or execute focused CPU validation and independent review.'
 if name.endswith('.md'):return 'Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules.'
 if name.endswith('.json'):return 'Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run.'
 if name.endswith('.py'):return 'Connect inherited CPU validation/build harnesses to packet37 additions.'
 return 'Retain packet-local implementation or validation support required by the merged runtime.'
def main():
 rows=[]
 for path in sorted(HERE.rglob('*')):
  relative=path.relative_to(HERE)
  if not path.is_file() or any(part in {'build','inherited-packet32','__pycache__'} for part in relative.parts):continue
  if str(relative) in {'INTEGRATE.md','integrate-files.json'}:continue
  old=BASE/relative;current=path.read_bytes();before=old.read_bytes() if old.exists() else None
  if before==current:continue
  rows.append(dict(path=str(relative),status='added' if before is None else 'changed',reason=reason(str(relative)),packet32_sha256=hashlib.sha256(before).hexdigest() if before is not None else None,packet37_sha256=hashlib.sha256(current).hexdigest()))
 report=dict(schema='packet37.integration-files.v1',base='packet32-pipeline',base_commit='2e8ec7585c',files=rows,exclusions=['ignored build scratch','inherited-packet32 provenance directory','INTEGRATE.md and integrate-files.json inventory outputs'])
 (HERE/'integrate-files.json').write_text(json.dumps(report,indent=2)+'\n')
 preamble='''# Packet36 and packet37 integration

Base: packet32-pipeline, commit `2e8ec7585c`. Packet36 and packet37 must be
merged onto that common base; no other packet is a runtime base. The inventory
below compares actual local bytes, and `integrate-files.json` stores hashes.
Regenerate after the final edit with
`nice -n 19 ionice -c 3 python -B integration_inventory.py` from this directory.
Build scratch and copied historical receipts are excluded from source merge
work. Historical receipts moved under `inherited-packet32/` retain their own
identity and are not packet37 evidence.

Packet36 contributes its draft provider on rank1. Preserve packet37's owner,
backend and prepared command layer when merging. The primary intersecting
files are `main.cpp`, `rank.hpp`, `pipeline.py`, `CMakeLists.txt`, `window.py`,
the CPU gates, and receipt schemas. Merge the draft-provider calls into the
existing rank1 protocol boundary, not into captured target launch objects.
Any provider scratch allocation or upload must finish before target replay;
never replace a captured target pointer or free its owner while a command can
still use it. Both parity launch sets belong to the target's transaction.
Draft proposals cannot advance the committed position, append to target KV,
or choose rollback state; target verification and packet32 commit/rollback
rules remain authoritative. The draft must release its own resources without
altering rank0's lookup residency. Preserve unchanged target arithmetic and
uncompressed cache throughout the merge.

Keep packet37's two complete prepared binding sets when draft guesses are
wrong. Select the set for the current alternate-buffer parity at each half,
then preserve packet32's rollback/swap decision. Regenerate plans only at a
quiescent boundary if an allocation identity or graph changes. Rerun the
argument-block comparisons in all modes, forced-miss and rollback-state
gates, both fresh K1 owners, the real-model oracle modes, and provider-specific
identity gates after the merge. K2 timing from this packet does not certify a
later draft merge's speed or quality.

A native controller is a separate implementation, not included here. It needs
the same two rank-owner lifetimes, bounded IPC protocol, stop propagation,
transaction IDs, guess requests, target verification, parity-aware half-run
ordering, rollback acknowledgement, error/fault handling and final resource
release. It must forward affinity and coordinator library paths, retain the
host and pipeline receipts, and expose diagnostic all-hit/all-miss injections.
Move scheduling and receipt collection out of Python without moving target
arithmetic or accepting unverified draft tokens. Prove the native controller
against the current mini and real-model token/layer/state oracles before any
performance comparison. A controller speedup remains unmeasured here.

## File-by-file changes

| File | Change | Reason |
| --- | --- | --- |
'''
 table=''.join('| `'+r['path']+'` | '+r['status']+' | '+r['reason']+' |\n' for r in rows)
 table+='| `INTEGRATE.md` | added | Human-readable merge instructions and generated inventory. |\n| `integrate-files.json` | added | Machine-readable hashes and reasons for every changed source/evidence file. |\n'
 (HERE/'INTEGRATE.md').write_text(preamble+table)
 print(f'{len(rows)} changed/new files inventoried')
if __name__=='__main__':main()
