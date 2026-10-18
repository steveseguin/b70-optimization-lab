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
 # The SELECTED packet100 draft is mtp36, not the optional packet59 schedule.
 # Retain p104_draft above for provenance; never use it as the selected baseline.
 s=(P/'mtp_kernels.cpp').read_text();s=s[:s.index('static void extent(')]
 s=s.replace('namespace mtp36 {','namespace p104mtpbase {\nusing Linear=mtp36::Linear;')+'}\n'
 (P/'p104_mtp_base.hpp').write_text('#pragma once\n'+s)
 s=s.replace('namespace p104mtpbase {','namespace p104mtp {')
 s=s.replace('#include "mtp_kernels.hpp"','#include "mtp_kernels.hpp"\n#include "p104_layout.hpp"')
 s=replace(s,'const uint8_t* w,const uint16_t* x,unsigned l){','const uint8_t* w,const uint16_t* x,unsigned l,size_t source=0){')
 s=replace(s,'if constexpr(!Int8)return p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);','''if constexpr(!Int8){float sum=0;
  for(unsigned tile=l*8;tile<K;tile+=256){unsigned stop=tile+8<K?tile+8:K;
   for(unsigned k=tile;k<stop;++k){float value=iq3::decode(iq3::Type::BF16,p104::draft_address<K,false>(w,source,k*2),0);float input=iq3::bits_float(uint32_t(x[k])<<16);float product=value*input;sum=sum+product;}
  }return sum;}''')
 s=replace(s,'w+K+(k/16)*4','p104::draft_address<K,true>(w,source,K+(k/16)*4)')
 s=replace(s,'iq3::signed8(w[k])','iq3::signed8(*p104::draft_address<K,true>(w,source,k))')
 s=replace(s,'(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb','(size_t(r.expert_id)*b.rows+r.row_begin+row)')
 s=replace(s,'lane<K,Int8>(b.w+off,x,l)','lane<K,Int8>(b.w,x,l,off)')
 s=replace(s,'lane<K,Int8>(b.peer+off,x,l)','lane<K,Int8>(b.peer,x,l,off)')
 (P/'p104_mtp.hpp').write_text('#pragma once\n'+s)
 # Selected shared-down is packet33's one-subgroup BF16 operation.
 s=(P/'p33_submit.cpp').read_text();s=s[:s.index('#ifndef OWN_RT_HOST_ONLY\nstruct Finish')]
 s=s.replace('namespace p33 {','namespace p104sharedbase {\nusing namespace p33;')+'}\n'
 (P/'p104_shared_base.hpp').write_text('#pragma once\n'+s)
 s=s.replace('namespace p104sharedbase {','namespace p104shared {')
 s=s.replace('#include "p33_submit.hpp"','#include "p33_submit.hpp"\n#include "p104_layout.hpp"')
 # A copy of the original scalar BF16 branch, retaining pragma, order and tree.
 s=s.replace('using namespace p33;','''using namespace p33;
 template<unsigned K>inline float tile_lane(const uint8_t*w,const uint16_t*x,unsigned begin,unsigned end,unsigned lane,size_t source){
  float sum=0;
  for(unsigned tile=begin+lane*8;tile<end;tile+=256){
   #pragma unroll
   for(unsigned j=0;j<8;++j)if(tile+j<end){float value=iq3::decode(iq3::Type::BF16,p104::draft_address<K,false>(w,source,(tile+j)*2),0);float input=iq3::bits_float(uint32_t(x[tile+j])<<16);float product=value*input;sum=sum+product;}
  }return sum;
 }
''')
 s=replace(s,'(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb)','(r.expert_id*d.rows+r.row_begin+row)')
 s=replace(s,'dense_lane<T,K>(d.w+source,d.x,unsigned(range.first),unsigned(range.second),lane)','tile_lane<K>(d.w,d.x,unsigned(range.first),unsigned(range.second),lane,source)')
 s=replace(s,' p28::Bound b{};',' static_assert(T==iq3::Type::BF16 && K==640 && Split==1);\n p28::Bound b{};')
 (P/'p104_shared.hpp').write_text('#pragma once\n'+s)
 print('address-only kernel derivatives generated')
if __name__=='__main__':main()
