"""Auditable address-only deltas from the packet100 source copies.

No parent output, selection, orchestration or build receipt is an input.
"""
from build_engine import P,limits
def replace(s,a,b):
 assert a in s,a
 return s.replace(a,b)
def main():
 limits()
 # Keep both baseline half conversion and accepted exact FP32 half cache.
 for cached in (False,True):
  namespace='p104iq2hc' if cached else 'p104iq2'
  s=(P/('p90_expert.hpp' if cached else 'p65_expert.hpp')).read_text()
  start=s.index('template<Type T,unsigned K,unsigned V,bool Packed=false>inline std::array<float,V> wide_chains')
  stop=s.index('template<Type T,unsigned K,unsigned WG,bool Prefetch,bool Wide=false,unsigned Followup=0>struct Kernel')
  chains=s[start:stop]
  # p65 has other helpers after wide_chains; use only wide_chains.
  if not cached:chains=chains[:chains.index('template<Type T,unsigned K,unsigned V>inline std::array<float,V> p73_deep_chains')]
  chains=replace(chains,'const uint8_t*w,const uint16_t*x,unsigned physical','const uint8_t*w,size_t source,const uint16_t*x,unsigned physical')
  rb=840 if cached else 820
  chains=replace(chains,'w+step*64+physical*16',f'p104::address(w,source,{rb},0,16,step*64+physical*16)')
  chains=replace(chains,'w+l.high+step*8+physical*2',f'p104::address(w,source,{rb},640,2,step*8+physical*2)')
  chains=replace(chains,'w+l.scales+step*8+physical*2',f'p104::address(w,source,{rb},720,2,step*8+physical*2)')
  unit=4 if cached else 2
  chains=replace(chains,f'w+l.halves+{unit}*step',f'p104::address(w,source,{rb},800,{unit},{unit}*step)')
  if not cached:
   a=chains.index('  }else{\n   static_assert(V==16);')
   chains=chains[:a]+'  }else{static_assert(T==Type::IQ2_S);}\n }return sums;\n}\n'
  kernel=s[stop:]
  a=kernel.index(' static std::array<float,V> chains(');b=kernel.index('#ifdef OWN_RT_HOST_ONLY',a)
  kernel=kernel[:a]+''' static std::array<float,V> chains(const uint8_t*w,size_t source,const uint16_t*x,unsigned lane){return wide_chains<T,K,V>(w,source,x,lane);}
'''+kernel[b:]
  kernel=replace(kernel,'(stream?b.peer:b.w)+source*b.rb','(stream?b.peer:b.w),source')
  kernel=kernel[:kernel.rfind('}')]
  (P/(namespace+'.hpp')).write_text('#pragma once\n#include "p104_layout.hpp"\n#include "p90_expert.hpp"\nnamespace '+namespace+' {\nusing iq3::Type;using p65::RawTile;using '+('p90exp' if cached else 'p65')+'::decode_tile;\n'+chains+kernel+'}\n')
 # Draft keeps the full operation, including paired activation and status.
 s=(P/'p59_draft.hpp').read_text()
 s=replace(s,'namespace p59 {','namespace p104draft {')
 s=replace(s,'#include "mtp_kernels.hpp"','#include "mtp_kernels.hpp"\n#include "p104_layout.hpp"')
 s=replace(s,'unsigned end=K){','unsigned end=K,size_t source=0){')
 s=replace(s,'reinterpret_cast<const uint16_t*>(w)+k','reinterpret_cast<const uint16_t*>(p104::draft_address<K,I>(w,source,2*k))')
 s=replace(s,'w+K+4*(k/16)','p104::draft_address<K,I>(w,source,K+4*(k/16))')
 s=replace(s,'w+k,8','p104::draft_address<K,I>(w,source,k),8')
 s=replace(s,'w+2*(k+j)','p104::draft_address<K,I>(w,source,2*(k+j))')
 s=replace(s,'unsigned physical,unsigned part){','unsigned physical,unsigned part,size_t source=0){')
 s=replace(s,'physical*V+c,begin,end)','physical*V+c,begin,end,source)')
 s=replace(s,'(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb','(size_t(r.expert_id)*b.rows+r.row_begin+row)')
 for w in ('w','peer'):
  for lane in ('l','physical'):
   s=replace(s,f'chain(b.{w}+off,x,{lane},part)',f'chain(b.{w},x,{lane},part,off)')
 (P/'p104_draft.hpp').write_text(s)
 # Q8 HC keeps the original two-row operation and fused four-stream mix.
 s=(P/'p73_hc.hpp').read_text().replace('namespace p73hc {','namespace p104hc {')
 s=s.replace('#include "p60_math.hpp"','#include "p60_math.hpp"\n#include "p104_layout.hpp"')
 s=replace(s,'unsigned lane){','unsigned lane,size_t source=0){')
 s=replace(s,'const auto*p=w+row*rb;','const auto r=source+row;')
 s=replace(s,'p+k+4','p104::address(w,r,rb,0,8,k)+4')
 s=replace(s,'p+k','p104::address(w,r,rb,0,8,k)')
 s=replace(s,'p+320+4*(k/32)','p104::address(w,r,rb,320,4,4*(k/32))')
 s=replace(s,'chains(b.gate_w+r*rb,b.act,lane)','chains(b.gate_w,b.act,lane,r)')
 (P/'p104_hc.hpp').write_text(s)
 print('address-only kernel derivatives generated')
if __name__=='__main__':main()
