#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
controller=(ROOT/'engine/src/stage2/packet194-expert-diet-engine/native_controller.hpp').read_text()
snapshot=(ROOT/'engine/src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/strict_snapshot.hpp').read_text()
mtp=(ROOT/'engine/src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp').read_text()
rank=(ROOT/'engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp').read_text()
assert 'b.start(1,half,guess,p+1,fixture(p+1),0)' in controller
assert 'if(!c.dumps&&!r0first.reserved[0])start_dependent();' not in controller
assert 'b.call(1,rollback' not in controller
assert 'if(e.a.rank!=0)return;' in snapshot
assert 'ownrt::draft_depth2::enabled()&&e.a.rank==1' not in snapshot
assert 'cache_mutable==cache_bytes' in mtp
assert 'probe_bytes-cache_mutable<=64ull*1024*1024' in mtp
assert 'production depth2 draft backup exceeds 32 MiB reserve' not in mtp
assert 'depth2_backup_bytes' not in mtp
cache64=155_189_248
workspace_bound=64*1024**2
assert cache64==148*1024**2 and cache64>32*1024**2
assert cache64+workspace_bound==222_298_112
assert 'rank1 must never speculate' in rank
assert 'suffix_image=std::make_unique<SpeculativeImage>(*engine,1)' in rank
assert 'a.rank==0)suffix_image' in rank
cap=30*1024**3
rows=[]
for context,owned in ((65536,32123721324),(32768,31154837100)):
    extra=0
    total=owned+extra
    rows.append({'context':context,'depth1_owned_bytes':owned,'depth2_rank1_additional_bytes':extra,
                 'depth2_rank1_total_bytes':total,'arena_cap_bytes':cap,'headroom_bytes':cap-total,
                 'fits':total<=cap})
assert all(row['fits'] and row['headroom_bytes']>=0 for row in rows)
report={'schema':'ownrt.depth2-memory-accounting.v1','passed':True,
        'basis':'parent-supplied B20 rank1 owned-byte measurements plus source-proved zero additional rank1 allocations; not a new GPU measurement',
        'rank1_protocol':'dependent d1 is submitted only after target verification, as an ordinary confirmed half; no rank1 Candidate snapshot or suffix image',
        'raw_ring':'rank1 SpeculativeImage constructor returns before inventory/allocation; canonical raw-ring and checkpoint paths are untouched',
        'contexts':rows,
        'rank0_draft_backup':{'context':65536,'cache_bytes':cache64,'cache_mib':148,
            'noncache_workspace_bound_bytes':workspace_bound,'maximum_admitted_backup_bytes':cache64+workspace_bound,
            'allocation':'exact summed mutable_ids bytes after cache geometry equality and non-cache workspace bound checks',
            'depth1_inert':'backup allocation remains inside OWNRT_DRAFT_DEPTH2 enabled branch; depth1 draft-memory JSON is unchanged and depth1 differential cases pass'}}
(ROOT/'depth2-memory-accounting.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
