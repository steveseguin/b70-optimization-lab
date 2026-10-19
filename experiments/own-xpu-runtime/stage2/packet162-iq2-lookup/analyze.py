"""CPU-only grid analysis; reads source/receipts, never weights or device APIs."""
import collections
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import resource

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STAGE = P.parent


def limits():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))


def save(name, value):
    (P / name).write_text(json.dumps(value, indent=2) + '\n')


def grid():
    import re
    path = STAGE / 'packet2/kernels/grids.hpp'
    body = path.read_text().split('iq2_s_grid[] = {')[1].split('};')[0]
    words = [int(x, 16) for x in re.findall(r'0x([0-9a-f]+)', body)]
    assert len(words) == len(set(words)) == 1024
    digits = [tuple({8: 0, 25: 1, 43: 2}[(w >> (8*j)) & 255]
                    for j in range(8)) for w in words]
    return words, digits


def circuit(digits, order):
    """Shared reduced ordered Boolean DAG, with constants as node 0/1."""
    nodes, unique = [], {}

    # Reorder the truth table once, so each split removes the low coordinate.
    permuted = [sum(((i >> d) & 1) << bit for d, bit in enumerate(order))
                for i in range(1024)]

    def ordered(values, depth):
        if all(v == values[0] for v in values):
            return values[0]
        lo, hi = ordered(values[::2], depth+1), ordered(values[1::2], depth+1)
        if lo == hi:
            return lo
        key = (depth, lo, hi)
        if key not in unique:
            unique[key] = len(nodes) + 2
            nodes.append(key)
        return unique[key]

    roots = [ordered(tuple((digits[i][j] >> b) & 1 for i in permuted), 0)
             for j in range(8) for b in range(2)]
    for i in range(1024):
        values = [0, 1]
        for depth, lo, hi in nodes:
            values.append(values[hi] if i & (1 << order[depth]) else values[lo])
        assert [values[roots[2*j]] + 2*values[roots[2*j+1]] for j in range(8)] == list(digits[i])
    return nodes, roots


def enumerative(words, digits):
    """11-bit supergrid: shape, middle-position combination, high combination.

    All original words lie in 2,054 permutations of sixteen (middle,high)
    count pairs. Remove six unused words, leaving a 2,048-entry supergrid.
    Six threshold additions undo the removal; combinatorial unranking is
    integer-only and uses immediate binomial rows, not the IQ2 table.
    """
    shapes = sorted(set((r.count(1),r.count(2)) for r in digits))
    universe=[]
    entries=[]
    for middle, high in shapes:
        start=len(universe)
        def mask_rank(mask):
            positions=[i for i in range(8) if mask & (1<<i)]
            return sum(math.comb(p,j+1) for j,p in enumerate(positions))
        middle_masks=sorted((sum(1<<p for p in c) for c in itertools.combinations(range(8),middle)),key=mask_rank)
        high_masks=sorted((sum(1<<p for p in c) for c in itertools.combinations(range(8-middle),high)),key=mask_rank)
        for m in middle_masks:
            for h in high_masks:
                row=[];q=0
                for j in range(8):
                    if m & (1<<j):row.append(1)
                    else:row.append(2*((h>>q)&1));q+=1
                universe.append(tuple(row))
        entries.append((start,len(universe),middle,high,len(high_masks)))
    assert len(universe)==2054 and len(set(universe))==2054
    originals=set(digits)
    holes=[i for i,r in enumerate(universe) if r not in originals][:6]
    kept=[r for i,r in enumerate(universe) if i not in holes]
    assert len(kept)==2048 and originals <= set(kept)
    mapping={r:i for i,r in enumerate(kept)}
    code=[mapping[r] for r in digits]
    lines=['#pragma once','#include <cstdint>','namespace p162enum {',
           'inline unsigned choose_mask(unsigned rank,unsigned k,unsigned n){',
           ' unsigned mask=0;']
    for p in reversed(range(8)):
        packed=sum(math.comb(p,k)<<(7*k) for k in range(p+1))
        lines += [f' if ({p}<n) {{',
                  f'  unsigned count=unsigned((0x{packed:x}ull>>(7*k))&127);',
                  f'  unsigned take=rank>=count; mask|=take<<{p}; rank-=take*count;k-=take;', ' }']
    lines += [' return mask;','}', 'inline uint64_t grid(unsigned code){',' unsigned r=code;']
    for hole in holes:lines.append(f' r+=r>={hole};')
    lines += [' unsigned middle=0,high=0,mrank=0,hrank=0;']
    for i,(start,end,m,h,radix) in enumerate(entries):
        lines += [f' {"if" if i==0 else "else if"} (r<{end}) {{',
                  f'  unsigned local=r-{start};middle={m};high={h};mrank=local/{radix};hrank=local%{radix};',' }']
    lines += [' unsigned m=choose_mask(mrank,middle,8),h=choose_mask(hrank,high,8-middle);',
              ' uint64_t result=0;unsigned q=0;',
              ' for(unsigned j=0;j<8;++j){unsigned is_middle=(m>>j)&1;',
              '  unsigned d=is_middle?1:2*((h>>q)&1);q+=1-is_middle;',
              '  result|=uint64_t(8+17*d+(d>>1))<<(8*j);}',
              ' return result;','}',
              'inline constexpr uint16_t encode[1024]={'+','.join(map(str,code))+'};','}']
    (P/'enum_grid.hpp').write_text('\n'.join(lines)+'\n')
    original=(STAGE/'packet136-record-bundle/p90_expert.hpp').read_text()
    candidate=original.replace('namespace p90exp {','namespace p162enumexp {')
    candidate=candidate.replace('p90::expert_stride(K)','(p90::expert_stride(K)+K/64)')
    needle='uint32_t a=p42expert::iq2_words[2*index],b=p42expert::iq2_words[2*index+1];'
    candidate=candidate.replace(needle,'uint64_t grid=p162enum::grid(index|(t.b<<10));uint32_t a=uint32_t(grid),b=uint32_t(grid>>32);')
    needle='float values[8];decode_tile<T>(t,k,values,decoded);'
    assert candidate.count(needle)==1
    candidate=candidate.replace(needle,'t.b=(w[p90::expert_stride(K)+step*4+physical]>>chain)&1;'+needle)
    (P/'enum_candidate.hpp').write_text('#include "enum_grid.hpp"\n'+candidate)
    return dict(supergrid_entries=2054,removed_unused_indices=holes,encoded_entries=2048,
                original_entries=1024,bits_per_tile=11,row_bytes=880,
                extra_bytes_per_rank=40*512*640*2*24,
                original_grid_sha256=hashlib.sha256(b''.join(w.to_bytes(8,'little') for w in words)).hexdigest())


def main():
    limits()
    words, digits = grid()
    # Fixed small search, not model tuning: all 1,024 normative codewords.
    orders = [tuple(range(10)), tuple(reversed(range(10)))]
    orders += [tuple(range(i, 10)) + tuple(range(i)) for i in range(1, 10)]
    candidates = [(len(circuit(digits, o)[0]), o) for o in orders]
    count, order = min(candidates)
    nodes, roots = circuit(digits, order)
    lines = ['#pragma once', '#include <cstdint>', 'namespace p162 {',
             '// Exhaustively generated from the pinned normative grid, no indexed table.',
             'inline uint64_t logic_grid(unsigned index) {',
             ' const unsigned n0=0,n1=1;']
    for depth in range(10):
        lines.append(f' const unsigned b{depth}=(index>>{order[depth]})&1;')
    for n, (depth, lo, hi) in enumerate(nodes, 2):
        lines.append(f' const unsigned n{n}=n{lo} ^ ((0u-b{depth}) & (n{lo} ^ n{hi}));')
    lines += [' uint64_t result=0;']
    for j in range(8):
        lines.append(f' const unsigned d{j}=n{roots[2*j]}+2*n{roots[2*j+1]};')
        lines.append(f' result |= uint64_t(8+17*d{j}+(d{j}>>1)) << {8*j};')
    lines += [' return result;', '}', '}']
    (P / 'logic_grid.hpp').write_text('\n'.join(lines)+'\n')
    source = STAGE / 'packet136-record-bundle/p90_expert.hpp'
    original = source.read_text()
    needle = 'uint32_t a=p42expert::iq2_words[2*index],b=p42expert::iq2_words[2*index+1];'
    assert original.count(needle) == 1
    candidate = original.replace('namespace p90exp {', 'namespace p162exp {').replace(
        needle, 'uint64_t grid=p162::logic_grid(index);uint32_t a=uint32_t(grid),b=uint32_t(grid>>32);')
    (P / 'candidate.hpp').write_text('#include "logic_grid.hpp"\n'+candidate)
    # Lossless lookup-free radix-3 expansion. Arithmetic proof covers every code.
    ternary = [sum(d*3**j for j, d in enumerate(row)) for row in digits]
    for code, row in zip(ternary, digits):
        assert tuple((code//3**j)%3 for j in range(8)) == row
    shape_counts = collections.Counter((r.count(1), r.count(2)) for r in digits)
    enum_report = enumerative(words,digits)
    plan = STAGE / 'packet136-record-bundle/memory-plan.json'
    headroom = json.loads(plan.read_text())['placements']['1']['capacities']['4096']['ranks'][1]['arena_headroom_bytes']
    rows_per_layer = 512*640*2
    encodings = []
    for name, bits in [('unsigned-byte magnitudes', 64), ('two-bit magnitudes', 16),
                       ('radix3 eight magnitudes', 13), ('parity-constrained radix3', 12)]:
        extra_row = (bits-10)*320//8
        per_layer = extra_row*rows_per_layer
        fraction = min(1.0, headroom/(per_layer*24))
        encodings.append(dict(name=name, magnitude_bits_per_eight=bits,
                              extra_bytes_per_row=extra_row,
                              extra_bytes_per_layer=per_layer,
                              extra_bytes_per_rank=24*per_layer,
                              whole_layers_fit=min(24, headroom//per_layer),
                              optimistic_fractional_coverage=fraction,
                              uniform_cost_grid_saving_ceiling_ms=0.57*fraction,
                              uniform_cost_class_time_ratio_floor=1-(0.57/1.456)*fraction))
    inputs = [source, plan, STAGE/'packet2/kernels/grids.hpp',
              STAGE/'packet99-iq2-grid/DIAGNOSIS.md',
              STAGE/'packet99-iq2-grid/evidence/micro-B/qualification.json',
              ROOT/'notes/2026-10-18-own-runtime-packet86-verdict.md',
              ROOT/'notes/2026-10-18-own-runtime-packet141-result.md']
    save('evidence/analysis.json', dict(
        schema='packet162.cpu-analysis.v1', device_executed=False,
        grid_entries=len(words), grid_bytes=8192, all_grid_digits_and_logic_exact=True,
        radix3_exact=True, all_grid_middle_digit_parity_even=all(r.count(1)%2==0 for r in digits),
        parity_supergrid_entries=(3**8+1)//2,
        shape_union_supergrid_entries=sum(math.comb(8,a)*math.comb(8-a,b) for a,b in shape_counts),
        circuit_nodes=count, circuit_order=order,
        enumerative=enum_report,
        circuit_trials=[dict(nodes=c, order=o) for c,o in candidates],
        nominal_boolean_operations=3*count, max_decision_depth=10,
        arena_headroom_bytes=headroom, expansions=encodings,
        source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}))
    print(json.dumps(dict(grid_exact=True, circuit_nodes=count,
                          nominal_boolean_ops=3*count, headroom=headroom)))


if __name__ == '__main__':
    main()
