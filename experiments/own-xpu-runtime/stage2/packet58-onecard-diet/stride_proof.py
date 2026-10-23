#!/usr/bin/env python3
"""Packet58-onecard-diet STOP proof: packet193's exp-diet header cannot be registered in the one-card dispatch as-is.

CPU only, no compiler. Pins (sha256) the five source files that fix both row formats, asserts the load-bearing
source lines are present verbatim, and transcribes the two constexpr layout formulas:

  one card  p49bgemv::layout(IQ2_S,2560)            -> 820-B rows, 16-bit halves at halves+2*step, decoded through the
                                                        65,536-entry halfcache table (p[19]); rows reached through
                                                        p58::resolve(..., indirect) (expert-cache pointer slots)
  two cards p90::expert_stride(2560)=halves+4*(k/256) -> 840-B rows, FP32 halves at halves+4*step, direct pointers,
                                                        19 bindings; p193diet::GateUp binds through p90exp::Kernel and
                                                        p90exp::validate requires b.rb == 840

Writes evidence/layout-mismatch.json. Exit 1 if any pinned line is missing (the proof would then be stale).
"""
import hashlib, json, sys, time
from pathlib import Path

P = Path(__file__).resolve().parent
S2 = P.parent
FILES = {
    'onecard_layout': S2 / 'packet58j-onecard-port/p49b_gemv.hpp',
    'onecard_virtual_bind': S2 / 'packet58j-onecard-port/p49d_expert.hpp',
    'onecard_kernel': S2 / 'packet58-onecard-cache23/native/generated/p58ag_expert.hpp',
    'onecard_dispatch': S2 / 'packet58-onecard-cache23/native/generated/p58ag_submit.cpp',
    'onecard_entry': S2 / 'packet58-onecard-cache23/native/generated/main.cpp',
    'onecard_selection': S2 / 'packet58-onecard-cache23/runtime-selection.json',
    'onecard_chain_selection': S2 / 'packet58-onecard-cache23-chain/runtime-selection.json',
    'twocard_layout': S2 / 'packet193-expert-diet/native-pinned/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p90_layout.hpp',
    'twocard_kernel': S2 / 'packet194-expert-diet-engine/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p90_expert.hpp',
    'diet_header': S2 / 'packet193-expert-diet/p193_diet.hpp',
    'packet194_dnr': S2 / 'packet194-expert-diet-engine/DO-NOT-REPEAT.md',
}
LINES = {
    'onecard_layout': [
        'else if(t==Type::IQ2_S){at=k/4;l.high=align16(at);at=l.high+k/32;l.scales=align16(at);at=l.scales+k/32;l.halves=align16(at);at=l.halves+2*(k/256);}',
        'l.row_bytes=(t==Type::IQ2_S||t==Type::IQ4_NL)?(at+3)&~size_t(3):align16(at);return l;',
        'std::memcpy(dst+l.halves+block*2,s,2);',
    ],
    'onecard_virtual_bind': ['b.rb=p49bgemv::layout(T,K).row_bytes;'],
    'onecard_kernel': [
        'const auto bits=p49bgemv::load16(w+l.halves+2*step);float decoded=halfcache?halfcache[bits]:iq3::half(bits);',
        'b.halfcache=Cached?static_cast<const float*>(p[19]):nullptr;',
        'p58::resolve(stream?b.peer:b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect)',
        'template<Type T,unsigned K,unsigned WG,bool Prefetch,bool Wide=false,unsigned Followup=0,bool Cached=true>struct Kernel final:p49b::Base {',
    ],
    'onecard_dispatch': [
        'std::array<ownrt::Allocation,20> ids{',
        'p58ag_exp::Kernel<T,K,64,false,true,0,Cached> k;',
        'p39::validate<T,K,E,Split>(bound);',
        'extent(halfcache,65536*4);',
        'k.indirect=b.indirect;',
    ],
    'onecard_entry': [
        'p58ag::expert(dev(c),selected,b,halfcache,a.experts=="wide64+halfcache")',
        'b.indirect=caching()&&(l.op=="expert_gate_up"||l.op=="routed_gemv");',
        'halfcache=allocate(0,"exact-half-decode-table",65536*4,Category::weights,Lifetime::process);',
    ],
    'twocard_layout': ['inline constexpr size_t expert_stride(unsigned k){return p49bgemv::layout(iq3::Type::IQ2_S,k).halves+4*(k/256);}'],
    'twocard_kernel': [
        'auto b=base.bind(p);b.rb=p90::expert_stride(K);return b;',
        'if(b.rb!=expected||uint64_t(b.experts)*b.rows*b.rb>UINT32_MAX)throw std::invalid_argument("p39 row stride/offset");',
        'float decoded=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step));',
        'chains((stream?b.peer:b.w)+source*b.rb,b.x+(paired?0:slot*K),physical)',
    ],
    'diet_header': [
        'using Production=p90exp::Kernel<Type::IQ2_S,2560,64,false,true>;',
        'p39::Bound bind(std::span<void*const>p)const{Production base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);}',
        'const float d=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step));',
        'chains((stream?b.peer:b.w)+source*b.rb,b.x,physical)',
    ],
    'packet194_dnr': ['**Do not screen the diet on a non-halfcache gate/up layout.** The diet is a diet of `p90exp::Kernel<IQ2_S,2560,64,wide>`'],
}


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def align16(x):
    return (x + 15) & ~15


def onecard_layout_iq2s(k):
    # verbatim transcription of p49bgemv::layout(Type::IQ2_S,k) (pinned line above)
    at = k // 4
    high = align16(at); at = high + k // 32
    scales = align16(at); at = scales + k // 32
    halves = align16(at); at = halves + 2 * (k // 256)
    row_bytes = (at + 3) & ~3
    return dict(codes=0, high=high, scales=scales, halves=halves, row_bytes=row_bytes, halves_bytes_per_step=2)


def twocard_stride(k):
    # verbatim transcription of p90::expert_stride(k) (pinned line above)
    return onecard_layout_iq2s(k)['halves'] + 4 * (k // 256)


def main():
    pins, missing = {}, []
    for key, path in FILES.items():
        text = path.read_text()
        pins[key] = dict(path=str(path), sha256=sha(path), lines_asserted=len(LINES.get(key, [])))
        for line in LINES.get(key, []):
            if line not in text:
                missing.append((key, line))
    sel = json.loads(FILES['onecard_selection'].read_text())
    chain_sel = json.loads(FILES['onecard_chain_selection'].read_text())
    one = onecard_layout_iq2s(2560)
    two = twocard_stride(2560)
    report = dict(
        schema='packet58diet.layout-mismatch.v1', passed=False, device_executed=False, compiler_runs=0,
        checked_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        verdict='STOP: packet193 exp-diet (p193diet::GateUp) is a diet of the two-card p90exp kernel on 840-byte FP32-expanded '
                'rows with direct pointers and 19 bindings; the one-card record line dispatches p58ag_exp::Kernel on 820-byte '
                'rows with 16-bit halves decoded through the halfcache table (binding 20) and indirect expert-cache pointer slots. '
                'The header cannot be registered as-is; a one-card diet would be a new kernel (re-derivation), which the brief forbids.',
        onecard=dict(record_selection_experts=sel['experts'], chain_selection_experts=chain_sel['experts'],
                     kernel='p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached=true>', dispatch='p58ag::expert (p58ag_submit.cpp)',
                     row_layout=one, bindings=20, halves_decode='halfcache[bits] (65,536-entry exact FP32 table, p[19])',
                     pointer_resolution='p58::resolve(base, offset, span, b.indirect) over p58::Pointer slots', validate='p39::validate (rb = layout.row_bytes)'),
        twocard=dict(kernel='p90exp::Kernel<IQ2_S,2560,64,false,true> (packet103/136/189/194 record gate/up)',
                     row_stride_bytes=two, halves_bytes_per_step=4, halves_decode='bits_float(load32(w+halves+4*step)) (FP32 expanded at load)',
                     bindings=19, pointer_resolution='direct: (stream?peer:w)+source*rb', validate='p90exp::validate (requires rb == expert_stride)'),
        diet=dict(header='packet193-expert-diet/p193_diet.hpp', pinned_sha256=pins['diet_header']['sha256'],
                  binds_through='p90exp::Kernel::bind -> rb = 840', reads_halves='load32(w+l.halves+4*step)', indirect_support=False, halfcache_binding=False),
        mismatch=dict(row_stride_bytes=[one['row_bytes'], two], halves_bytes_per_step=[one['halves_bytes_per_step'], 4], bindings=[20, 19],
                      pointer_resolution=['indirect p58::Pointer slots', 'direct'], validate=['p39::validate rb==820', 'p90exp::validate rb==840']),
        premise_check=dict(claim='"the one-card line uses the same expert dispatch tables as the two-card record (one-card synthesis 1 diffed them byte-identical)"',
                           finding='the byte-identical table is dispatch-speed6.json (packet26 dense/registry classes); the expert gate/up kernel is chosen by the '
                                   'selection key experts=wide64+halfcache -> p58ag::expert, outside that table'),
        pins=pins, missing_lines=[dict(file=k, line=l) for k, l in missing])
    report['passed'] = not missing
    out = P / 'evidence/layout-mismatch.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], onecard_row_bytes=one['row_bytes'], twocard_stride=two, missing=len(missing))))
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
