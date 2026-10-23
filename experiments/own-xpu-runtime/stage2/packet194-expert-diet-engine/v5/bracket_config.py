"""Packet194 rows: one k3x+diet smoke and one k3x / k3x+diet one-load bracket (the k3x record line is the in-load control).

Lineages (v5/lineage/<name>/selection.json):
  v3          packet187's record selection (0-25 storage, 16 keys): CPU gates only;
  v3k         packet189's V3 views of the k3 storage (19 keys): CPU gates only;
  k3x-record  packet189's k3x selection byte for byte (19 keys, c5443bbf...; expert_gateup absent = production): the record
              selection of packet190 (62.345282 tok/s). CPU gates only (identity proofs); a 19-key load cannot switch to a 20-key view;
  k3x         the bracket's CONTROL: k3x-record + expert_gateup production (20 keys): the record gate/up kernel, same storage,
              same execution flags; the full-shape gate proves its captures equal the record storage's;
  k3x-diet    the CANDIDATE: k3x + expert_gateup diet (20 keys): packet193's exact gate/up instruction diet at every exp-halfcache
              gate/up site; nothing else differs (0 B of allocation).
Queue rows (each depends on the previous one, same lane):
  0 smoke   k3x-diet  incident64 + 12 cold x 64 tokens, exact, first-request data proof
  1 bracket k3x       one load, views k3x/k3x-diet/k3x/k3x-diet/k3x (in-load gate/up kernel switch), 5 x (incident64 + 12 x 128);
                      decides s194_decision over rows 0-1 (the ruling: screen +0.5 %, chain +2 % AND >= 63.592 tok/s)
"""
from common import HERE,ROOT,P56,read,require,sha,module
VALUES=('v3','v3k','k3x-record','k3x','k3x-diet')
K3_VARIANTS=('v3k','k3x-record','k3x','k3x-diet')
ROWS=(dict(index=0,kind='smoke',variant='k3x-diet',config='row0-smoke-k3x-diet.json',name='row0-smoke-k3x-diet'),
      dict(index=1,kind='bracket',variant='k3x',config='row1-bracket-k3x-diet.json',name='row1-bracket-k3x-diet'))
KINDS=('smoke','view','bracket')
HOST_BASE=97*1024**3+1200*1024**2
# Host shadow of the V3 dual layout's extra device bytes (packet186 full-shape census delta, rank 0 + rank 1):
HOST_V3_EXTRA=2_100_819_444+155_750_384
# packet188 k3 storage (unchanged in packet189/194; the diet adds 0 B): + GDN layer 26 on rank 0 (full-shape census delta) + pinned kernel-io staging (both ranks)
CENSUS_DELTA_K3=(1_129_070_858,0)
KIO_PINNED=86_016+73_728  # rank 0 (token + lookup staging) + rank 1 (sync staging only), full-shape census
HOST_K3_EXTRA=HOST_V3_EXTRA+CENSUS_DELTA_K3[0]+CENSUS_DELTA_K3[1]+KIO_PINNED
# Expected seconds from packet189's recorded lane-B rows (lanequeue-B36, 2026-10-22): k3x smoke ~313 s (first row, cold), one-load
# V3/k3x bracket 475.7 s. The k3 storage and request mix are identical; the diet only shortens gate/up kernels.
EXPECTED={0:[270,420],1:[460,900]}

def row(index):
 require(index in range(len(ROWS)),'registered packet194 row index required')
 return ROWS[index]

def host_required(variant):
 return HOST_BASE+(HOST_K3_EXTRA if variant in K3_VARIANTS else HOST_V3_EXTRA)

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
                v3_layout=('rank 0 holds 0-26 (k3 storage), rank 1 holds 24-47 + full head; boundary=%s kernel_io=%s rank0_prepare=%s boundary_export=%s expert_gateup=%s'%(choices['boundary'],choices['kernel_io'],choices['rank0_prepare'],choices['boundary_export'],choices.get('expert_gateup','production (absent)'))
                           if k3 else 'rank 0 holds 0-25, rank 1 holds 24-47 + full head; boundary=%s'%choices['boundary']),
                reason=('packet194 k3 storage (packet188/189\'s, unchanged; the diet adds 0 B): packet186 V3 dual ledger plus the measured full-shape census delta (rank0 +%d B, rank1 +%d B; v5/evidence/full-shape.json)'%CENSUS_DELTA_K3
                        if k3 else 'packet186 V3 dual layout (packet187 record selection): packet186 ledger, census identical (v5/evidence/full-shape.json)'),
                configuration=configuration,memory_gate=str(P56/'memory_gate.py'),memory_gate_sha256=sha(P56/'memory_gate.py'))
 return dict(placement=placement,timing='token',timing_modes=['token'],lineage=str(line),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),binary_sha256=sha(binary),
             dispatch=str(dispatch),dispatch_sha256=sha(dispatch),profile='tp2',selection_sha256=sha(line/'selection.json'),memory_plan_sha256=sha(line/'memory-plan.json'),
             host_required_available_bytes=host_required(line.name))
