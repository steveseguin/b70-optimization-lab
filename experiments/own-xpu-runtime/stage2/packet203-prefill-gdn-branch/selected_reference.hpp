#pragma once
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49c_kernel.hpp"
namespace p203_selected {
// Selected p42 cooperative gated_norm statement body; only branch selection fixed.
inline void norm_group(ng::Shape s,ng::Args a,int group,ng::HostTeam t){
 using namespace ng;constexpr auto Code=gated_norm;
 // slots 15/17/18 = sticky_error/position/active; slot16 = RoPE; no readback.
 t.each(1,[&](int){t.x[0]=float(!a.i(18)[0]||t.error(a));});t.barrier();
 if(t.x[0])return;
 t.barrier();
 int pos=a.i(17)[0];
 if(pos<0||pos>s.capacity-s.tokens){if(group==0)t.each(1,[&](int){t.fail(a);});return;}
 bool unit=s.flags&1;
  int width=Code==gated_norm?128:s.width,stream=group%s.heads,base=group*width;
  auto value=[&](int k){if(Code!=combine_norm)return a.b(0,base+k);return Args::bf(a.b(0,base+k)+a.b(1,(group/s.heads)*width+k)*(2.f*sigmoid(a.b(2,group)/4.f)));};
  float inv=detmath::rsqrt(tree(t,width,[&](int k){float x=value(k);return x*x;})/float(width)+1e-6f);t.barrier();
  t.each(width,[&](int k){float x=value(k);int wslot=Code==combine_norm?3:Code==gated_norm?2:1;
   float y=(x*inv)*(a.weight(wslot,(Code==gated_norm?0:stream*width)+k,s.flags)+float(unit));
   if constexpr(Code==gated_norm)y=y*sigmoid(a.b(1,base+k));
   a.put(Code==combine_norm?5:Code==gated_norm?3:2,base+k,y);if constexpr(Code==combine_norm)a.put(4,base+k,x);});
}
}
