#pragma once
#include "../packet3/step/plan.hpp"
#include "../packet13-integrate/performance.hpp"
#include "../packet10-kopt5/kernels.hpp"
#include "reference.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "backend.hpp"
#endif
namespace iq3::tp14 {
using Matrix=kopt4::Matrix;using Launch=kopt4::Launch;
Launch expert_gate_up(ownrt::Device&,const Matrix&,const Matrix&,unsigned=1);
Launch expert_down(ownrt::Device&,const Matrix&,unsigned=1);
}
namespace tp2 {
inline bool expandable(iq3::Type type,const flash::Launch& l,bool mini) {
  // All packet13 variants use eight-consecutive products and adjacent-pair
  // trees. Preserve the full-shape split count; raw F32/BF16 stay byte-identical.
  (void)type;(void)l;return !mini;
}
inline integrated::Launch dense(ownrt::Device& d,const integrated::Matrix& m,unsigned v,bool expanded) {
  if(!expanded)return integrated::dense(d,m,v);
#ifdef OWN_RT_HOST_ONLY
  struct Op final:integrated::HostOperation {
    integrated::Matrix m;unsigned split;
    void run(std::span<void* const> p)const override {
      auto rb=iq3::expanded::row_bytes(m.type,m.columns);
      for(unsigned r=0;r<m.rows;++r)static_cast<uint16_t*>(p[2])[r]=iq3::bf16_bits(iq3::expanded::row(m.type,static_cast<uint8_t*>(p[0])+r*rb,static_cast<uint16_t*>(p[1]),iq3::Type::BF16,m.columns,split));
    }
  }op;op.m=m;op.split=v==1||v>=4?4:1;std::array ids{m.w,m.x,m.y};auto e=d.compute(op,ids,{});return {e,e,1};
#else
  return iq3::expanded::gemv(d,m,v==1||v>=4?4:1);
#endif
}
inline integrated::Launch experts(ownrt::Device& d,const std::vector<integrated::Matrix>& m,bool shared) {
#ifdef OWN_RT_HOST_ONLY
  return integrated::experts(d,m,shared);
#else
  if(m[0].type==iq3::Type::F32)return integrated::experts(d,m,shared);
  return shared?iq3::tp14::expert_gate_up(d,m[0],m[1]):iq3::tp14::expert_down(d,m[0]);
#endif
}
}
