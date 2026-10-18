"""Copy committed packet103 sources; derive the isolated mtp36 load-only arm."""
import hashlib,json,re,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
SOURCE=P.parent/'packet103-record-bundle'
HELPER=P.parent/'packet104-tile-transpose'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    from build_engine import limits
    limits()
    origins={}
    def copy(src,dst):
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():raise RuntimeError('refuse overwrite: '+str(dst))
        shutil.copyfile(src,dst)
        origins[str(dst.relative_to(P))]={'source':str(src.relative_to(ROOT)),'sha256':sha(src)}
    # Keep all local header dependencies in this packet, with shared platform
    # headers remaining hash-bound inputs through the checked include mirror.
    pending=[SOURCE/'mtp_kernels.cpp',SOURCE/'owner_api.hpp',SOURCE/'prepared_submission.hpp']
    seen=set()
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src)
        copy(src,P/src.relative_to(SOURCE))
        for name in re.findall(r'^\s*#include\s*"([^"\n]+)"',src.read_text(),re.M):
            candidate=next((q for q in (src.parent/name,SOURCE/name) if q.is_file()),None)
            if candidate and candidate.resolve().is_relative_to(SOURCE):pending.append(candidate.resolve())
    for name in ('kernel_guard.hpp','kernel_overlay.py','submission_overlay.py','jit_smoke.cpp'):
        if not (P/name).exists():copy(SOURCE/name,P/name)
    for name in ('math_gate.py','kernel_gate.py','route_inputs.py','run_micro.py','qualification.py','shared-wrapper-pin.json'):
        copy(HELPER/name,P/name)
    copy(P.parent/'packet94-hc-norm-fusion/compile_turn.py',P/'compile_turn.py')
    for name in ('route-inputs.json.gz','routes.bin'):
        copy(HELPER/'evidence'/name,P/'evidence'/name)
    text=(P/'mtp_kernels.cpp').read_text()
    body=text[:text.index('static void extent(')]+'}\n'
    base='#pragma once\n'+body.replace('namespace mtp36 {','namespace p108base {\nusing Linear=mtp36::Linear;',1)
    (P/'p108_base.hpp').write_text(base)
    candidate=base.replace('namespace p108base {','namespace p108 {',1)
    start=candidate.index(' else {float sum=0;for(unsigned tile=l*8;')
    end=candidate.index('\n}',start)
    new=''' else {
  static_assert(K==640||K==2560,"packet108 INT8 production shapes only");
  float sum=0;
  for(unsigned tile=l*8;tile<K;tile+=256){
   // Eight contiguous values have one original FP32 scale (groups of 16).
   // Only raw loads change. The scale*code, value*x and sum additions retain
   // their original types, order and rounding boundaries, including NaNs.
   uint32_t scale_bits;std::memcpy(&scale_bits,w+K+(tile/16)*4,4);
   uint32_t words[2];
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,2> codes;
   codes.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+tile)));
   words[0]=codes[0];words[1]=codes[1];
   sycl::vec<uint16_t,8> inputs;
   inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+tile));
#else
   std::memcpy(words,w+tile,8);
#endif
   for(unsigned j=0;j<8;++j){
    const uint8_t code=uint8_t(words[j/4]>>(8*(j%4)));
    float value=iq3::bits_float(scale_bits)*float(iq3::signed8(code));
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits=x[tile+j];
#endif
    float product=value*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
   }
  }
  return sum;
 }'''
    candidate=candidate[:start]+new+candidate[end:]
    (P/'p108_loads.hpp').write_text(candidate)
    (P/'source-origin.json').write_text(json.dumps(dict(parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),copies=origins,derivation='mtp_kernels.cpp prefix through Dense, namespace only in baseline; candidate INT8 lane raw loads only; same WG128/SG32, stores, status and tree'),indent=2)+'\n')
    # Helpers inherit the established safe mirror and lane admission, never
    # the frozen packet's build or output directory.
    path=P/'run_micro.py';s=path.read_text().replace("summary.get('candidate_count') == 9","summary.get('candidate_count') == 2").replace('packet104','packet108')
    s=s.replace('import micro_gate\n        micro_gate.evaluate(P)','import qualification\n        qualification.evaluate(P)')
    path.write_text(s)
    path=P/'qualification.py';path.write_text(path.read_text().replace('packet104','packet108'))
    options=json.loads((HELPER/'compiler.snapshot.json').read_text())
    options=[s.replace(str(HELPER),str(P)) for s in options]
    (P/'compiler.snapshot.json').write_text(json.dumps(options,indent=2)+'\n')
    print('Copied packet103 source closure and derived load-only draft kernels; no device work.')
if __name__=='__main__':main()
