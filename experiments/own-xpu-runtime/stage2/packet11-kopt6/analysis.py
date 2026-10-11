#!/usr/bin/env python3
"""Count retained native hot regions; explicit unverified issue-rate scenarios."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re
HERE=Path(__file__).resolve().parent
NAMES=('experts_sg32','register_grid','slm_pair','packed_pipeline')
def instructions(text):
    return [l for l in text.splitlines() if re.search(r'\(\d+\|M\d+\)',l) and not l.lstrip().startswith('//')]
def opcode(line):return re.sub(r'^\([^)]*\)\s*','',line.strip()).split()[0]
def calculate():
    receipt=json.loads((HERE/'assembly-receipt.json').read_text())
    regions=[];rows=[]
    for t,block_bytes in [('IQ2_S',82),('IQ3_S',110)]:
        text=gzip.decompress((HERE/f'build/isa-evidence/packet9-{t}-v0.asm.gz').read_bytes()).decode()
        blocks=re.split(r'(?=// B\d+:)',text)
        selected=[b for b in blocks if re.match(r'// B(141|142):',b)]
        if len(selected)!=2:raise ValueError('native labels changed; read ISA and update region map')
        body=''.join(selected);lines=instructions(body);counts=collections.Counter(map(opcode,lines))
        # SIMD32 costs two SIMD16 issue slots; split SIMD16 instructions cost one.
        issue=sum(max(1,int(re.search(r'\((\d+)\|',l)[1])/16) for l in lines)
        regions.append(dict(type=t,blocks=['B141','B142'],scope='one octet/lane: grid-index/address/lookup and finite signed decode; excludes activation, block/subscale, loop and reduction',
            native_instructions=len(lines),simd16_issue_equivalents=issue,opcode_counts=dict(sorted(counts.items())),
            integer_to_float=sum(bool(re.search(r'\bmov .*:f\s+.*:(w|uw|d|ud)\b',l)) for l in lines),
            byte_extracts_semantic=8,sign_applications_semantic=8,weight_scale_mul=8,
            table_loads=1 if t=='IQ2_S' else 2,
            representative_native_lines=[l.strip() for l in lines if 'load.' in l or 'r[a0.' in l][:8],
            excerpt_sha256=hashlib.sha256(body.encode()).hexdigest()))
        (HERE/'build/isa-evidence'/f'baseline-{t}-finite-region.txt').write_text(body)
        for v,name in enumerate(NAMES):
            # Count each candidate's actual finite native basic blocks too.
            native=gzip.decompress((HERE/f'build/isa-evidence/packet11-{t}-v{v}.asm.gz').read_bytes()).decode()
            cblocks=re.split(r'(?=// B\d+:)',native)
            ids=[141,142] if v<2 else ([199] if t=='IQ2_S' else [200]) if v==2 else [283]
            cbody=''.join(b for b in cblocks if any(b.startswith(f'// B{i}:') for i in ids))
            clines=instructions(cbody)
            if not clines:raise ValueError('candidate finite block map changed')
            cissue=sum(max(1,int(re.search(r'\((\d+)\|',l)[1])/16) for l in clines)
            (HERE/'build/isa-evidence'/f'candidate-{t}-v{v}-finite-region.txt').write_text(cbody)
            # Baseline/register regions exclude all 8 products + 8 adds.
            # Pair/pipeline regions include seven; the common successor
            # contains the last product/add (four SIMD16 issue slots).
            tail=32 if v<2 else 4
            # Outside-region costs remain assumptions, explicitly separate from
            # counted instructions: activation loads, scales, loop/reduction;
            # new regions also exclude grid fetch, addressed by +64 slots.
            overhead=96 if v<2 else 160
            setup=(64 if t=='IQ2_S' else 16) if v==1 else (32 if t=='IQ2_S' else 8) if v==2 else 0
            slots=cissue+tail+overhead+setup
            issue_gbs=256*1.5*block_bytes/slots
            # Exposed lookup wait/issue underfill + occupancy. Explicit guesses,
            # deliberately penalize the observed 6016-byte IQ2 register spill.
            utilization=(.55,.85) if v==0 else ((.20,.45) if t=='IQ2_S' else (.45,.75)) if v==1 else (.55,.85) if v==2 else (.65,.90)
            ranges=[min(590,issue_gbs*u) for u in utilization]
            kernel=next(k for k in receipt['kernels'] if k['source']=='packet11' and k['type']==t and k['variant']==v)
            rows.append(dict(type=t,variant=name,simd16_issue_slots_per_256_weight_block=slots,
                native_blocks=ids,native_region_instructions=len(clines),native_region_simd16_slots=cissue,
                common_accumulation_tail_slots=tail,outside_region_issue_assumption=overhead,setup_amortized=setup,
                issue_only_GB_s=issue_gbs,utilization_assumption=list(utilization),predicted_GB_s=ranges,
                configured_grf=kernel['configured_grf'],spill_metadata=[s for s in kernel['spill_metadata'] if s.startswith('//.spill')]))
    return dict(schema='own-runtime.iq3.packet11.issue-forecast.v1',measured=False,
        assembly_receipt_sha256=hashlib.sha256((HERE/'assembly-receipt.json').read_bytes()).hexdigest(),
        assumptions=dict(verified=False,vector_engines=256,simd_lanes=16,issue_instructions_per_engine_cycle=1,clock_GHz=1.5,
            max_GB_s=590,constant_lookup_latency_cycles=[40,200],slm_lookup_latency_cycles=[20,40],
            register_shuffle_latency_cycles=[4,12],latency_note='Hypotheses only: native send/dependency annotations do not encode elapsed latency. Cache hits, conflicts and occupancy unmeasured.'),
        formula='issue GB/s = 256 engines * 1.5 GHz * packed block bytes / SIMD16 issue slots per SG32 block; multiply explicit utilization scenario; cap590',
        limitation='Native region counts are static ISA counts. Outside-region costs, schedule, latency, utilization and GHz are unverified. No end-to-end or model-speed verdict.',
        native_regions=regions,predictions=rows)
if __name__=='__main__':
    data=calculate();(HERE/'analysis.json').write_text(json.dumps(data,indent=2)+'\n')
    for r in data['predictions']:print(r['type'],r['variant'],r['simd16_issue_slots_per_256_weight_block'],[round(x,1) for x in r['predicted_GB_s']])
