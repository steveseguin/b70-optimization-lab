// Frozen production oracle compiled in a distinct namespace to avoid C++ ODR
// collisions with packet58's changed classes. Parent sources stay untouched.
#define p49dvirtual p58oracle49d
#define p49b p58oracle49b
#define p39 p58oracle39
#include "../packet49d-round3/p49d_expert.hpp"
#undef p49dvirtual
#undef p49b
#undef p39
extern "C" void p58_production(unsigned kind,unsigned rows,unsigned count,unsigned experts,void**p){
 if(kind==0){p58oracle49d::GateKernel k;k.rows=rows;k.count=count;k.experts=experts;k.run({p,18});}
 else if(kind==2){p58oracle49d::DownKernel k;k.rows=rows;k.count=count;k.experts=experts;k.run({p,18});}
 else {p58oracle39::Bound b{};b.rows=rows;b.count=count;b.experts=experts;b.rb=1100;
  b.w=static_cast<const uint8_t*>(p[0]);b.peer=static_cast<const uint8_t*>(p[1]);b.x=static_cast<const uint16_t*>(p[2]);b.y=static_cast<uint16_t*>(p[3]);b.py=static_cast<uint16_t*>(p[4]);b.routes=static_cast<const iq3::Route*>(p[5]);b.status=static_cast<uint32_t*>(p[6]);b.peer_status=static_cast<uint32_t*>(p[7]);b.error=static_cast<uint32_t*>(p[16]);b.active=static_cast<const uint32_t*>(p[17]);
  p58oracle39::host_gemv<iq3::Type::IQ3_S,2560,p58oracle39::Kind::expert_checks,true,1>(b);
 }
}
