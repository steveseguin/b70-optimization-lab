"""Expand the actual CPU capture using the explicit device-only finish stages."""
import collections,copy,json,re,tarfile,gzip
from build_engine import P,ROOT,sha,save,limits
def footprint(x):
    # Binding footprint is an admitted address span, NOT measured memory traffic.
    bs={b['id']:b for b in x['bindings']}
    excludes=('operator-scratch','gemv-workspace','rope-v2','parallel-controls')
    bound=sum(b['bytes'] for b in bs.values())
    working=sum(b['bytes'] for b in bs.values() if not any(v in b['label'] for v in excludes))
    if '.expsgate' in x['label'] or '.expsdown' in x['label']:
        for b in bs.values():
            if ':weight:' in b['label']:working-=b['bytes']-b['bytes']//512*10
    kernel=x['kernel'];suffix=re.sub(r'^blk\.\d+\.','',x['label'])
    useful=None;meaning='distinct admitted bindings excluding reusable arenas; selected 10/512 expert banks'
    if suffix=='route':
        useful=1024+40+40+120+120+576*4;meaning='router + IDs/probabilities/routes + occupied global scratch, unique bytes'
        if kernel.startswith('p109route::'):
            useful+=3*640*2;meaning+=' + shared gate/up/activation'
    elif suffix=='shexpact':useful=3*640*2;meaning='two BF16 inputs + BF16 activation output'
    elif suffix=='expsact':useful=3*640*10*2;meaning='two BF16 inputs + BF16 activation output'
    elif suffix=='moe' and kernel=='integrated::Combine':useful=10*2560*2+10*4+2560*2;meaning='ten BF16 rows + FP32 probabilities + rounded mixture'
    elif suffix=='moe':useful=2560*6+2+4;meaning='rounded mixture + shared down + gate + one + output'
    elif suffix=='ffn.combine':useful=4*2560*4+2560*2+8;meaning='streams read/write + branch + inject'
    elif kernel.startswith('p49c::attention-combine finish'):useful=2560*16+2560*2+4*2560*4+8;meaning='four partials per row + attention output + streams read/write + inject'
    elif kernel.startswith('p28::split4 finish'):useful=x['shape'][1]*18;meaning='four FP32 partials + BF16 output per row'
    return dict(bound_bytes=bound,working_binding_bytes=working,useful_bytes=useful,byte_definition=meaning,low_byte=(useful if useful is not None else working)<=65536)
def expand(rows):
    result=[]
    for item in rows:
        x=copy.deepcopy(item);result.append(x)
        # p49c_submit.cpp:24-25 emits a second kernel only in the SYCL build.
        if x['kernel'].startswith('p49c::DenseKernel') and '(p39::Kind)4,' in x['kernel']:
            finish=copy.deepcopy(x);finish['kernel']='p49c::attention-combine finish (device-only)';finish['command']+=1;finish['device_only_source']='packet103-record-bundle/p49c_submit.cpp:24';result.append(finish)
        # p28 Split4/RPG1 has an explicit device-only finish as well.
        if re.search(r'p28::Kernel<.*?, 4u, 1u, (?:true|false), (?:true|false)>',x['kernel']):
            finish=copy.deepcopy(x);finish['kernel']='p28::split4 finish (device-only)';finish['command']+=1;finish['device_only_source']='packet103-record-bundle/p28/submit.cpp:96';result.append(finish)
        if x['kernel'].startswith('p33::Kernel') and x['kernel'].endswith(', 4u>'):raise AssertionError('new p33 split finish requires census expansion')
    for i,x in enumerate(result):
        x.update(ordinal=i,queue_dependency=i-1 if i else None,**footprint(x))
    return result
def main():
    limits();report=json.loads((P/'evidence/full-shape.json').read_text());ranks={};pins={}
    for r in report['runs']:
        if r['fresh']:continue
        artifact=ROOT/r['artifact']['path'];assert sha(artifact)==r['artifact']['sha256'];pins[str(artifact.relative_to(ROOT))]=sha(artifact)
        with tarfile.open(artifact) as t:
            ranks[r['rank']]={view:expand(json.load(t.extractfile(name))) for view,name in [('production','launches-initial.json'),('fused','launches-view1.json')]}
        assert len(ranks[r['rank']]['production'])-len(ranks[r['rank']]['fused'])==72
    raw=json.dumps(dict(device_executed=False,source_pins=pins,ranks=ranks,scope='full-shape prepared target halves at initial context extent32; source-expanded device-only finishes; no timing measurement'),indent=2).encode()
    (P/'evidence/census.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    assert gzip.decompress((P/'evidence/census.json.gz').read_bytes())==raw
    lines=['# Packet109 launch and dependency census','',
      'Source: copied packet103 bundle, with route-fast, rec-both-plus, expert half-cache, down-tile16, wide HC and split32 draft attention. Every row below comes from actual allocation/capture startup on CPU; only model payload and backend are mocked. The raw bindings, logical inputs/outputs, and every source-expanded command are in [census.json.gz](evidence/census.json.gz).',
      '', 'All commands on a rank use its in-order queue. Thus each row depends on the preceding row as well as its listed logical inputs. Rank0 speculation and rank1 target run separate halves; no compute/compute overlap is assumed on one B70. A cancelled speculation can stop at any command boundary; this table is the completed half.',
      '', '**Bytes:** `bound` is the exact sum of distinct allocation extents bound to that command, including shared scratch and unused ABI placeholders. `working` excludes the shared scratch/rope/control arenas and scales routed banks to ten experts; it remains a binding-footprint upper bound, not DRAM bytes. `useful` is supplied only for the small fusion sites whose byte accesses were derived directly. Repeated loads and cache transactions are not inferred. `LOW` means at most 64 KiB by the useful count when known, otherwise the working footprint.',
      '', 'The CPU backend folds attention GEMV and its finish into one operation, and folds p28 Split4/RPG1 finishes too. The device sources add those launches, listed explicitly here. The resulting **636/628** rank0/rank1 counts exactly reconcile Packet108’s running baseline. The **matched change** in these captures is 72 launches on each rank.',
      '', '| Rank | CPU captures | Device-source production | Device-source fused | Removed |', '| --- | ---: | ---: | ---: | ---: |']
    for rank,views in ranks.items():lines.append(f'| {rank} | {sum("device_only_source" not in x for x in views["production"])} | {len(views["production"])} | {len(views["fused"])} | 72 |')
    lines+=['','## Fusion decisions','',
      '- Route top-k and normalized mixture weights already run inside packet78’s one-workgroup route. Fusing router GEMV into it would cross workgroups or serialize the dense projection. Do not reopen that form.',
      '- The small.ffn tuple writes router, shared gate/up and shared gate scalar before route. Shared SiLU/product needs only the gate/up rows, so it can run after route’s final barrier in the same workgroup. The unchanged route guarantees valid expert IDs for the later expert status checks. Both original activation inputs and the rounded activation output remain present.',
      '- Shared down is after expert down. The shared gate scalar is already written by small.ffn; its later plan site is empty. A row subgroup can therefore finish the same K640 Q8 dot, write BF16 down, compute slots0..9 in order, write BF16 mixture, and execute the original rounded shared blend. The subsequent HC combine stays separate. No phase reads another workgroup’s newly produced result.',
      '- No expert gate/up activation fusion: packet39 found predicate/register pressure in that loop. No descriptor interpreter, new reduction tree, NaN canonicalization, changed verifier, or cross-workgroup barrier is introduced.',
      '', '## Previous attempts checked','',
      'Every repository `DO-NOT-REPEAT.md` was searched; retained matches: [fusion-history.txt](evidence/fusion-history.txt).',
      '', '| Packet | Prior boundary | Why this proposal differs |','| --- | --- | --- |',
      '| 21 | Generic fusion; unsafe cross-workgroup producer/consumer; repeated CPU HC prologue | Two fixed shapes; routing stays one WG; downstream row-local inputs already exist |',
      '| 39 | Expert activation spills; down/mixture and HC norms require multiple rows; shared-up absorption disables small.ffn | Keep small.ffn; fuse already-complete ten-expert row inputs into shared-down, leaving HC norm alone |',
      '| 59 | Empty capture Sites must remain; draft arithmetic is distinct | Preserve empty original Sites and all draft choices; target-only fusion |',
      '| 69 | Fused argmax too small; expanded row stride includes metadata | No argmax campaign; shared-down stride checked against expanded::row_bytes =760 |',
      '| 77 | Historical timings cannot stand in for a current matched identity | Historical budget motivates work only; five-view in-engine bracket decides benefit |',
      '| 78 | Probability ties and reduction trees must be exact | Copy the selected route body unchanged; append activation after final phase |',
      '', 'At 3.4–5 microseconds per launch, 72 removals suggest 0.245–0.360 ms per half before added fusion work, overlap and engine transfer. This is an issue-cost hypothesis only. No gain, record or device quality is claimed.',
      '', '## Complete per-layer kernel inventory','',
      'Labels are full plan labels. The immediately preceding ordinal in the same rank is the queue dependency; `inputs` in the raw JSON gives the data dependency. Host-only operation names identify the corresponding native ng/Glue kernel family. All unselected plan sites have zero launches; they are retained for recapture.']
    for rank,views in ranks.items():
        lines+=['',f'### Rank {rank}: '+('speculative layers0–23' if rank==0 else 'target layers24–47 and head'),'', '| # | Layer/site | Kernel | Bound bytes | Working bytes | Useful bytes | Small |','| ---: | --- | --- | ---: | ---: | ---: | --- |']
        for x in views['production']:
            kernel=x['kernel'].replace('packet18::(anonymous namespace)::','p18::').replace('packet27::small::(anonymous namespace)::','p27::')
            lines.append(f'| {x["ordinal"]} | {x["label"]} | `{kernel}` | {x["bound_bytes"]} | {x["working_binding_bytes"]} | {x["useful_bytes"] if x["useful_bytes"] is not None else "—"} | {"LOW" if x["low_byte"] else ""} |')
    (P/'CENSUS.md').write_text('\n'.join(lines)+'\n')
    print('census saved: source-expanded production/fused',[(r,len(v['production']),len(v['fused'])) for r,v in ranks.items()])
if __name__=='__main__':main()
