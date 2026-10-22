"""Packet186 rows: one V3 smoke, two fresh-load bundle-8 controls bracketing one U/V3/U/V3/U one-load bracket.

Lineages (v5/lineage/<name>/selection.json):
  production  bundle 8 exactly (14 keys, target head split, rank 0 holds layers 0-23); fresh-load control rows;
  u           V3 dual layout (rank 0 also holds 24-25; full target head on rank 1), boundary=none: the un-split
              control executed exactly as packet185's unsplit views; the bracket LOADS this lineage;
  v3          the same storage with boundary=rank0 and snapshot_host=static: V3 (smoke row, bracket candidate).
Queue rows (each depends on the previous one, same lane):
  0 smoke   v3          incident64 + 12 cold x 64 tokens, exact, first-request data proof
  1 view    production  fresh load, incident64 + 12 x 128 (split-head control 0)
  2 bracket u           one load, views U/V3/U/V3/U (in-load boundary/snapshot switch), 5 x (incident64 + 12 x 128)
  3 view    production  fresh load, 12 x 128 (split-head control 1); decides s186_decision over rows 1-3
"""
from common import HERE,ROOT,P56,read,require,sha,module
VALUES=('production','u','v3')
ROWS=(dict(index=0,kind='smoke',variant='v3',config='row0-smoke-v3.json',name='row0-smoke-v3'),
      dict(index=1,kind='view',variant='production',config='row1-view-production.json',name='row1-control-production'),
      dict(index=2,kind='bracket',variant='u',config='row2-bracket-u-v3.json',name='row2-bracket-u-v3'),
      dict(index=3,kind='view',variant='production',config='row3-view-production.json',name='row3-control-production'))
KINDS=('smoke','view','bracket')
HOST_BASE=97*1024**3+1200*1024**2
# Host shadow of the V3 dual layout's extra device bytes (full-shape census delta, rank 0 + rank 1):
HOST_V3_EXTRA=2_100_819_444+155_750_384
CENSUS_DELTA=(2_100_819_444,155_750_384)
EXPECTED={0:[300,420],1:[200,330],2:[480,900],3:[200,330]}

def row(index):
 require(index in range(len(ROWS)),'registered packet186 row index required')
 return ROWS[index]

def host_required(variant):
 return HOST_BASE+(HOST_V3_EXTRA if variant in ('u','v3') else 0)

def sealed_identity(args):
 from cpu_seal import verify
 verify();line=args.lineage.resolve()
 require(line.parent==HERE/'lineage' and line.name in VALUES,'registered lineage required')
 require(args.profile=='tp2' and args.placement=='1' and args.timing=='token','fixed two-card token timing required')
 binary=HERE/'build/device/own-rt-iq3';dispatch=line/'dispatch-speed6.json';seal=line/'screen-seal.json'
 for value,path in ((args.binary,binary),(args.dispatch,dispatch),(args.seal,seal)):require(value is None or value.resolve()==path,'sealed input differs')
 gate=module('p186_memory',P56/'memory_gate.py');configuration=gate.configuration(read(line/'memory-plan.json'),4096,1,0)
 dual=line.name!='production'
 placement=dict(name='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[26,24] if dual else [24,24],context=4096,memory_admitted=True,supported=True,
                v3_layout='rank 0 holds 0-25, rank 1 holds 24-47 + full head; boundary=%s'%read(line/'selection.json')['choices']['boundary'] if dual else None,
                reason=('packet186 V3 dual layout: production ledger plus the measured full-shape census delta (rank0 +%d B, rank1 +%d B; v5/evidence/full-shape.json)'%CENSUS_DELTA
                        if dual else 'packet136 budget plus inherited packet153 probe scratch and 64 KiB reserve (bundle 8)'),
                configuration=configuration,memory_gate=str(P56/'memory_gate.py'),memory_gate_sha256=sha(P56/'memory_gate.py'))
 return dict(placement=placement,timing='token',timing_modes=['token'],lineage=str(line),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),binary_sha256=sha(binary),
             dispatch=str(dispatch),dispatch_sha256=sha(dispatch),profile='tp2',selection_sha256=sha(line/'selection.json'),memory_plan_sha256=sha(line/'memory-plan.json'),
             host_required_available_bytes=host_required(line.name))
