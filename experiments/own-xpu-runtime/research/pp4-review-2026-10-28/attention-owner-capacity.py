"""CPU retained-allocation screen; no inference, model loading or device contact."""
from pathlib import Path
import json,re,math,hashlib
ROOT=Path('/dev/shm/sc117-dedicated-3plus1-20261028-r3/output')
NATIVE=Path('/dev/shm/sc117-attention-owner-cpu-screen-20261028')
LAYER=re.compile(r'blk\.(\d+)\.')
CACHE={'keys','values','raw','pooled'};INTERNAL={'gate','q','kn','iqn','ids'}
SCRATCH={'card0:attention-scores:0','card0:attention-probabilities:0'}
LEGACY={'card0:speculative-private-image','card0:speculative-copy-table','card0:speculative-static-copy-table'}
CAP=30*1024**3;LIMIT=128*1024**2;ITEM=32
plans=[json.load(open(NATIVE/f'target{i}/native/launch-plan.json')) for i in (0,1)]
buffers={b['name']:b for p in plans for b in p['buffers']}
base={i:[] for i in range(48)};globals=[];sources=[];observed=[]
for i in (0,1,2):
 path=ROOT/f'stage{i}/native/census.json';c=json.load(open(path));layout=json.load(open(path.with_name('ring-checkpoint-layout.json')))
 sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 g=[]
 for row in c['allocations']:
  if row['memory']!='device' or not row['live']:continue
  m=LAYER.search(row['label'])
  if m:
   if not row['label'].startswith(('card0:alternate:','card0:speculative-reserve:')):base[int(m[1])].append(row)
  elif not row['label'].startswith('card0:ring:') and row['label'] not in LEGACY:g.append(row)
 globals.append(g);observed.append(layout)
temporal={i:[] for i in range(48)}
for p in plans:
 for launch in p['launches']:
  if launch['op'] in ('conv','gdn'):
   name=launch['outputs'][1];m=LAYER.search(name)
   if m and name not in temporal[int(m[1])]:temporal[int(m[1])].append(name)

def owner(begin,end,first,final,depth,remote=False,transport=0):
 rows=list(globals[0 if first else 2 if final else 1])
 for layer in range(begin,end):
  rows+=base[layer]
  if first:
   for name in temporal[layer]:
    for prefix in ('alternate:','speculative-reserve:'):
     rows.append(dict(label='card0:'+prefix+name,bytes=buffers[name]['bytes'],category='recurrent-state'))
 removed=[]
 if remote:
  kept=[]
  for row in rows:
   m=re.fullmatch(r'card0:blk\.\d+\.qsa\.(\w+)',row['label'])
   if row['label'] in SCRATCH or m and m[1] in CACHE|INTERNAL:removed.append(row)
   else:kept.append(row)
  rows=kept
 slot=table_rows=0
 for row in rows:
  if row['category']=='weights':continue
  m=re.fullmatch(r'card0:(blk\.\d+\.qsa\.(keys|values|raw|pooled))',row['label'])
  if m:
   b=buffers[m[1]];size=b['bytes']//b['shape'][0];n=1 if m[2]=='pooled' else depth
   slot+=size*n;table_rows+=n*math.ceil(size/LIMIT)
  else:slot+=row['bytes'];table_rows+=math.ceil(row['bytes']/LIMIT)
 if transport:slot+=transport;table_rows+=math.ceil(transport/LIMIT)
 tables=table_rows*ITEM*2;ring=depth*(slot+tables)
 # This is an explicit conservative budget, not a claim to reconstruct the
 # legacy image constructor: ring scope includes its mutable source superset.
 legacy_upper=(slot+1024**2) if first else 0
 physical=sum(r['bytes'] for r in rows)+transport
 return dict(begin=begin,end=end,packed_and_other_weight_bytes=sum(r['bytes'] for r in rows if r['category']=='weights'),
  base_device_bytes_before_ring_legacy=physical,removed_QSA_bytes=sum(r['bytes'] for r in removed),
  removed_allocations=[dict(label=r['label'],bytes=r['bytes']) for r in removed],
  ring_slot_bytes=slot,ring_table_rows=table_rows,ring_two_tables_per_slot_bytes=tables,
  ring_total_bytes=ring,legacy_image_and_tables_budget_bytes=legacy_upper,
  projected_device_bytes=physical+ring+legacy_upper,projected_margin_bytes=CAP-physical-ring-legacy_upper,
  current_per_slot_256MiB_pass=slot<=256*1024**2,current_aggregate_512MiB_pass=ring<=512*1024**2,
  current_table_rows4096_pass=table_rows<=4096)

validation=[]
for i,(a,b) in enumerate(((0,17),(17,33),(33,48))):
 got=owner(a,b,i==0,i==2,3)
 actual=observed[i]
 assert got['ring_slot_bytes']==actual['slot_bytes'],(i,got['ring_slot_bytes'],actual['slot_bytes'])
 actual_table=actual['checkpoint_private_allocations'][1]['bytes']
 assert got['ring_two_tables_per_slot_bytes']==actual_table*2
 validation.append(dict(stage=i,slot_bytes=got['ring_slot_bytes'],table_bytes=actual_table,exact_match=True))

# Two bounded per-target slots:64KiB request,32KiB reply,4KiB metadata.
transport=2*(65536+32768+4096)
cases=[]
for cut in range(17,40):
 for depth in (2,3):
  targets=[owner(0,cut,True,False,depth,True,transport),owner(cut,48,False,True,depth,True,transport)]
  cases.append(dict(boundaries=[0,cut,48],depth=depth,targets=targets,
    peak_projected_bytes=max(t['projected_device_bytes'] for t in targets),
    capacity_projection_fits=all(t['projected_margin_bytes']>=0 for t in targets),
    current_ring_guards_pass=all(t['current_per_slot_256MiB_pass'] and t['current_aggregate_512MiB_pass'] and t['current_table_rows4096_pass'] for t in targets)))
best={str(depth):min((c for c in cases if c['depth']==depth),key=lambda c:c['peak_projected_bytes']) for depth in (2,3)}
current2={str(depth):[owner(0,25,True,False,depth),owner(25,48,False,True,depth)] for depth in (2,3)}
qsa=[b for n,b in buffers.items() if re.fullmatch(r'blk\.\d+\.qsa\.\w+',n)]
qsa_cache=sum(b['bytes'] for b in qsa if b['name'].split('.')[-1] in CACHE)
qsa_scratch=sum(b['bytes'] for b in qsa if b['name'].split('.')[-1] not in CACHE)
# Includes raw input duplicates and output Y on remote side; no full target cache remains.
remote_base=qsa_cache+qsa_scratch+12*3072+100663296+2*787584+8388608+12+2*transport
remote_slot=qsa_scratch+12*(6144+6144+1536+512)+2*787584+8388608+12+2*transport
# At most2target peers ×3 outstanding transaction versions; storage upper bound
# only. Correct implementation must partition versions by layer/transaction.
remote_snapshots=6*(remote_slot+2*4096*32)
remote=dict(cache_bytes=qsa_cache,per_layer_input_intermediate_output_bytes=qsa_scratch,
 norm_weight_duplicate_budget_bytes=12*3072,rope_bytes=100663296,attention_score_probability_bytes=2*787584,
 operator_scratch_budget_bytes=8388608,device_transport_bytes=2*transport,
 base_device_bytes=remote_base,snapshot_versions_budget=6,snapshot_storage_upper_bytes=remote_snapshots,
 projected_total_bytes=remote_base+remote_snapshots,projected_margin_bytes=CAP-remote_base-remote_snapshots)
result=dict(schema='ownrt.attention-owner-per-device-projection.v1',scope='CPU projection using actual native plans and live retained allocation census; no runtime fit or performance claim',
 actual_3stage_checkpoint_geometry_validation=validation,current_2plus1_no_offload=current2,
 best_balanced_attention_owner=best,remote_owner=remote,per_target_transport_bytes=transport,sources=sources,
 limitations=['Target base sums use actual per-layer allocation census, preserving all packedweights/projections/GDN/host-lookup roles. First-stage temporal alternate+reserve banks re-created from executed conv/gdn producers.',
 'Legacy first-stage image/table budget is conservative ring-slot superset plus1MiB metadata, not measured constructor demand. Driver/library shadow bytes remain unknown.',
 'Remote cache/scratch removal is explicit enumerated ownership, not current implemented native feature. Norm weights remain on targets; owner adds small duplicate readonly norms. Transport buffers and snapshot copies are charged.',
 'Remote six-version storage is an upper budget, not a correct global rollback protocol: layer/transaction partitioning is required to avoid reverting another target canonical update.',
 'Native two-target262K plan currently refuses30GiB before device initialization; no guards were bypassed. Offloaded projections do not authorize launches.'])
print(json.dumps(result,indent=2))
