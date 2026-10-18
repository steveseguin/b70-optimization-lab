"""Reproducible mechanical two-accumulator delta from packet65's wide64 body.

This writes only this new packet. The frozen production source is hash pinned
in production-sources.json. No compilation, model work or device access.
"""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
def main():
 source=P.parent/'packet65-expert-occupancy/p65_expert.hpp'
 original=source.read_text()
 (P/'production65.hpp').write_text(original)
 start=original.index('template<Type T,unsigned K,unsigned V>inline std::array<float,V> wide_chains')
 end=original.index('\ntemplate<Type T,unsigned K,unsigned WG',start)
 text=original[start:end]
 text=text.replace('std::array<float,V> wide_chains(const uint8_t*w,const uint16_t*x,unsigned physical)',
  'std::array<std::array<float,V>,2> wide_pair(const uint8_t*w,const uint16_t*x0,const uint16_t*x1,unsigned physical)')
 text=text.replace('std::array<float,V> sums{}','std::array<std::array<float,V>,2> sums{}')
 before='sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));'
 after='sycl::vec<uint16_t,8> a,b;a.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x0+k));b.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x1+k));'
 assert text.count(before)==2;text=text.replace(before,after)
 text=text.replace('uint16_t bits=inputs[j];','uint16_t bits0=a[j],bits1=b[j];').replace('uint16_t bits=x[k+j];','uint16_t bits0=x0[k+j],bits1=x1[k+j];')
 before='float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;'
 after='float p0=values[j]*iq3::bits_float(uint32_t(bits0)<<16);sums[0][chain]=sums[0][chain]+p0;float p1=values[j]*iq3::bits_float(uint32_t(bits1)<<16);sums[1][chain]=sums[1][chain]+p1;'
 assert text.count(before)==2;text=text.replace(before,after)
 (P/'production_expert_chains.hpp').write_text('#pragma once\n// Derived from packet65 wide64: all raw loads and decode_tile calls unchanged.\n#include "production65.hpp"\nnamespace p68c {\nusing p65::RawTile;using p65::decode_tile;\n'+text+'\n}\n')
 receipt={'schema':'packet68c.production-sources.v1','sources':{str(source.relative_to(P.parents[3])):hashlib.sha256(source.read_bytes()).hexdigest()},'expert_base':'packet65 wide64','reason':'Both lane quick screens pass all thirteen exact requests and beat their production controls; this is screen evidence, not full-chain qualification.'}
 for lane,index in [('A','02'),('B','05')]:
  p=P.parent/f'packet65-expert-occupancy/screen/evidence/p65-quick-{lane}-{index}-wide64/run/summary.json'
  r=json.loads(p.read_text());assert r['passed'] and r['incident64']['passed'] and r['request_count']==12
  receipt.setdefault('expert_screens',[]).append({'path':str(p.relative_to(P.parents[3])),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'exact_requests':13,'class_balanced_tok_s':r['class_balanced_tok_s_1_100_intervals_after_ttft']['median']})
 (P/'production-sources.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
