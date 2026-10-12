#pragma once
#include "../packet29-merged/kernels.hpp"
#include "../packet29-merged/runtime_kernels.hpp"
namespace route42ref {using namespace integrated;
struct Bound {
 Spec s;std::array<void*,32> p;
 View in(int j)const{return {p[j],s.sizes[j],s.types[j]};}
 View out(int j)const{int k=s.ni+j;return {p[k],s.sizes[k],s.types[k]};}
 int tail()const{return s.ni+s.no+s.nw;}
 uint32_t* error()const{return static_cast<uint32_t*>(p[tail()+1]);}
 uint32_t* position()const{return static_cast<uint32_t*>(p[tail()+2]);}
 uint32_t* active()const{return static_cast<uint32_t*>(p[tail()+3]);}
 uint32_t failed()const {
#ifdef OWN_RT_HOST_ONLY
  return *error();
#else
  return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error()).load();
#endif
 }
 void fail()const {
#ifdef OWN_RT_HOST_ONLY
  *error()=1;
#else
  sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error()).store(1);
#endif
 }
 // Validate before conversion: View::get can expose poisoned integer bytes as
 // a floating value outside int range. Invalid values never form an address.
 int safe_id(float value,int limit,int upper)const {
  if(!std::isfinite(value)||value<0||value>=float(limit)||value>float(upper)||std::floor(value)!=value){fail();return 0;}
  return int(value);
 }
 int safe_position()const {
  auto value=*position();if(value>=unsigned(s.g.context)){fail();return 0;}
  return int(value);
 }
};
template<int Width,class F> float subtree(int n,int begin,F get){
 float v[Width];int count=std::min(Width,n-begin);
 for(int i=0;i<count;++i)v[i]=get(begin+i);
 for(int stride=1;stride<Width&&stride<n;stride*=2)
  for(int i=0;i<count;i+=2*stride)v[i]=v[i]+(i+stride<count?v[i+stride]:0.f);
 return v[0];
}
bool simple_v2(const Spec& s){return s.special==Special::broadcast||(s.special==Special::normal&&(s.op==Op::route||s.op==Op::hc_combine||s.op==Op::expert_gather||s.op==Op::argmax));}
int simple_phases(const Spec& s){return s.op==Op::route?5:(s.op==Op::argmax||s.op==Op::expert_gather)?2:1;}
int simple_work(const Spec& s,int phase){
 if(s.op==Op::route){int n=s.sizes[0];return phase==0||phase==1?(n+15)/16:phase==2||phase==3?n:1;}
 if(s.op==Op::argmax)return phase==0?(s.sizes[0]+255)/256:1;
 if(s.op==Op::expert_gather&&phase==1)return 1;
 if(s.op==Op::expert_gather)return std::max(s.g.top,int(s.sizes[s.ni+2]));
 return s.sizes[s.ni];
}
template<Op Code,int Phase,int FixedN=0,int FixedTop=0> void simple_body(Bound b,int index){
 constexpr int phase=Phase;constexpr bool raw_rank=false;
 if(!*b.active()||b.failed())return;
 auto s=b.s;float* tmp=static_cast<float*>(b.p[b.tail()]);
 if constexpr(Code==Op::route){
  int n=FixedN?FixedN:int(b.in(0).n),top=FixedTop?FixedTop:s.site.shape[1],chunks=(n+15)/16;
  // tmp: maxima[chunks], subtree sums[chunks], exponentials[n], probabilities[n].
  float* sums=tmp+chunks;float* ex=sums+chunks;float* prob=ex+n;
  if(phase==0){float maximum=-INFINITY;for(int j=index*16;j<std::min(n,(index+1)*16);++j){float x=b.in(0).get(j);if(!std::isfinite(x)){b.fail();return;}maximum=std::max(maximum,x);}tmp[index]=maximum;}
  else if(phase==1){float maximum=-INFINITY;for(int j=0;j<chunks;++j)maximum=std::max(maximum,tmp[j]);
   sums[index]=subtree<16>(n,index*16,[&](int j){float v=detmath::exp(b.in(0).get(j)-maximum);ex[j]=v;return v;});
  }else if(phase==2){float den=subtree<256>(chunks,0,[&](int j){return sums[j];});prob[index]=ex[index]/den;}
  else if(phase==3){float v=prob[index];int rank=0;for(int j=0;j<n;++j)rank+=prob[j]>v||(prob[j]==v&&j<index);
   if(rank<top){b.out(0).put(rank,index);b.out(1).put(rank,v);if(s.no>=4)for(int k=0;k<3;++k){b.out(2).put(rank*3+k,k==0?index:k==1?0:s.g.mid);b.out(3).put(rank*3+k,k==0?index:k==1?0:s.g.h);}}
  }else if(!raw_rank){float sum=subtree<32>(top,0,[&](int j){return b.out(1).get(j);});for(int j=0;j<top;++j)b.out(1).put(j,b.out(1).get(j)/sum);}
 }else if constexpr(Code==Op::argmax){
  int n=b.in(0).n,chunks=(n+255)/256;
  if(phase==0){int best=index*256;bool finite=true;for(int j=best;j<std::min(n,(index+1)*256);++j){float v=b.in(0).get(j);finite=finite&&std::isfinite(v);if(v>b.in(0).get(best))best=j;}tmp[index]=float(best);tmp[chunks+index]=finite?0:1;}
  else{int best=0;bool bad=false;for(int j=0;j<chunks;++j){bad=bad||tmp[chunks+j]!=0;int id=int(tmp[j]);if(b.in(0).get(id)>b.in(0).get(best))best=id;}
   if(bad){best=0;for(int lane=0;lane<128;++lane){int local=lane;for(int j=lane;j<n;j+=128)if(b.in(0).get(j)>b.in(0).get(local))local=j;if(lane<n&&(b.in(0).get(local)>b.in(0).get(best)||(b.in(0).get(local)==b.in(0).get(best)&&local<best)))best=local;}}
   b.out(0).put(0,best);if(bad)b.fail();}
 }
 else if constexpr(Code==Op::hc_mix)b.out(0).put(index,b.in(0).get(index%b.in(0).n)); // dedicated broadcast instantiation
 else if constexpr(Code==Op::ple_add)b.out(0).put(index,b.in(0).get(index)+ng::Args::bf(b.in(1).get(index)+b.in(2).get(index)));
 else if constexpr(Code==Op::hc_combine)b.out(0).put(index,b.in(0).get(index)+b.in(1).get(index%s.site.shape[1])*(2.f*ng::sigmoid(b.in(2).get(index/s.site.shape[1])/4.f)));
 else if constexpr(Code==Op::expert_gather){
  if(phase==1){for(int j=0;j<s.g.top;++j)if(tmp[j])b.fail();return;}
  if(index<s.g.top){float v=b.in(0).get(index);bool valid=std::isfinite(v)&&v>=0&&v<float(s.g.experts)&&std::floor(v)==v;int id=valid?int(v):0;tmp[index]=valid?0:1;for(int k=0;k<3;++k){b.out(0).put(index*3+k,k==0?id:k==1?0:s.g.mid);b.out(1).put(index*3+k,k==0?id:k==1?0:s.g.h);}}
  // Unfused compatibility path only. Fused Rank has no repeated-row binding.
  if(!s.no_materialize_gather&&index<int(b.out(2).n))b.out(2).put(index,b.in(1).get(index%b.in(1).n));
 }
}

}
