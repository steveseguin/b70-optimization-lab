"""Packet191 rows: one k3x-on smoke and one k3x-off/on one-load bracket (a MEASUREMENT, not a screen).

Lineages (v5/lineage/<name>/selection.json):
  v3       packet187's record selection (rank0_layers 0-25, boundary rank0, static; 16 keys): no packet189 row loads it;
           packet188 row 1 (fresh V3, 60.50488520482965, hash-pinned, read in place) is the fresh reference;
  v3k      the k3 storage (rank0_layers 0-26: rank 0 also holds GDN layer 26) executed as V3 (boundary rank0, trims off,
           export copy); the bracket LOADS this lineage, its V3 views are the in-load record-line controls;
  k3x      the same storage with boundary rank0-k3 (24-26 on rank 0), kernel_io kernel, rank0_prepare async and
           boundary_export copy (the 20,480-byte export on the copy engine): the candidate;
  k3trims  packet188's candidate (boundary_export kernel), registered for CPU gates only; no device row.
Queue rows (each depends on the previous one, same lane):
  0 smoke   k3x   incident64 + 12 cold x 64 tokens, exact, first-request data proof
  1 bracket v3k   one load, views V3/k3x/V3/k3x/V3 (in-load boundary/trim/export switch), 5 x (incident64 + 12 x 128);
                  decides s191_report over rows 0-1 plus packet188's fresh V3 row 1
"""
from common import HERE,ROOT,P56,read,require,sha,module
VALUES=('v3','v3k','k3x','k3trims','k3x-off','k3x-on')
ROWS=(dict(index=0,kind='smoke',variant='k3x-on',config='row0-smoke-k3x-on.json',name='row0-smoke-k3x-on'),
      dict(index=1,kind='bracket',variant='k3x-off',config='row1-bracket-sites.json',name='row1-bracket-sites'))
KINDS=('smoke','view','bracket')
HOST_BASE=97*1024**3+1200*1024**2
# Host shadow of the V3 dual layout's extra device bytes (packet186 full-shape census delta, rank 0 + rank 1):
HOST_V3_EXTRA=2_100_819_444+155_750_384
# packet188 k3 storage (unchanged in packet189): + GDN layer 26 on rank 0 (full-shape census delta) + pinned kernel-io staging (both ranks)
CENSUS_DELTA_K3=(1_129_070_858,0)
KIO_PINNED=86_016+73_728  # rank 0 (token + lookup staging) + rank 1 (sync staging only), full-shape census
HOST_K3_EXTRA=HOST_V3_EXTRA+CENSUS_DELTA_K3[0]+CENSUS_DELTA_K3[1]+KIO_PINNED
# Expected seconds from packet189's recorded lane-B rows (lanequeue-B36, 2026-10-22, window.json elapsed_seconds): k3x smoke
# (first row, cold) and the one-load V3/k3x bracket; the k3x storage and request mix are identical, the on views add the sampled
# drain-time timestamp reads (<= 2 % of a sampled half, 24 of 127 fixtures).
EXPECTED={0:[270,420],1:[460,900]}

def row(index):
 require(index in range(len(ROWS)),'registered packet191 row index required')
 return ROWS[index]

def host_required(variant):
 return HOST_BASE+(HOST_K3_EXTRA if variant in ('v3k','k3x','k3trims','k3x-off','k3x-on') else HOST_V3_EXTRA)

def sealed_identity(args):
 from cpu_seal import verify
 verify();line=args.lineage.resolve()
 require(line.parent==HERE/'lineage' and line.name in VALUES,'registered lineage required')
 require(args.profile=='tp2' and args.placement=='1' and args.timing=='token','fixed two-card token timing required')
 binary=HERE/'build/device/own-rt-iq3';dispatch=line/'dispatch-speed6.json';seal=line/'screen-seal.json'
 for value,path in ((args.binary,binary),(args.dispatch,dispatch),(args.seal,seal)):require(value is None or value.resolve()==path,'sealed input differs')
 gate=module('p189_memory',P56/'memory_gate.py');configuration=gate.configuration(read(line/'memory-plan.json'),4096,1,0)
 k3=line.name!='v3';choices=read(line/'selection.json')['choices']
 placement=dict(name='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[27,24] if k3 else [26,24],context=4096,memory_admitted=True,supported=True,
                v3_layout=('rank 0 holds 0-26 (k3 storage), rank 1 holds 24-47 + full head; boundary=%s kernel_io=%s rank0_prepare=%s boundary_export=%s'%(choices['boundary'],choices['kernel_io'],choices['rank0_prepare'],choices['boundary_export'])
                           if k3 else 'rank 0 holds 0-25, rank 1 holds 24-47 + full head; boundary=%s'%choices['boundary']),
                reason=('packet189 k3 storage (packet188\'s, unchanged): packet186 V3 dual ledger plus the measured full-shape census delta (rank0 +%d B, rank1 +%d B; v5/evidence/full-shape.json)'%CENSUS_DELTA_K3
                        if k3 else 'packet186 V3 dual layout (packet187 record selection): packet186 ledger, census identical (v5/evidence/full-shape.json)'),
                configuration=configuration,memory_gate=str(P56/'memory_gate.py'),memory_gate_sha256=sha(P56/'memory_gate.py'))
 return dict(placement=placement,timing='token',timing_modes=['token'],lineage=str(line),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),binary_sha256=sha(binary),
             dispatch=str(dispatch),dispatch_sha256=sha(dispatch),profile='tp2',selection_sha256=sha(line/'selection.json'),memory_plan_sha256=sha(line/'memory-plan.json'),
             host_required_available_bytes=host_required(line.name))
