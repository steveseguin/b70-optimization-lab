#include "p30_submit.hpp"
#include "adapter.hpp"
#include "kernels.hpp"
#include "specialised_submit.hpp"
#include "round2_submit.hpp"
#include "p33r2.hpp"
#include "mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "native.hpp"
#include "sycl_operation.hpp"
#endif
namespace packet18 {
using namespace integrated;
namespace {
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
// Tiny geometry has the same equations, with dimensions taken from its plan.
// Keep these parallel as well: synthetic integration tests do not silently
// select the single_task exactness control.
template<class Team> void tiny(Bound b,int group,Team t) {
 const auto s=b.s;const auto g=s.g;
 // Snapshot the guard once per workgroup so another group's fail cannot make
 // lanes diverge around a barrier. The error itself is atomic across groups.
 t.each(1,[&](int){t.x[0]=float(!*b.active()||b.failed());});t.barrier();
 if(t.x[0])return;t.barrier();
 auto bf=[](float x){return ng::Args::bf(x);};
 auto weight=[&](int w,int k){return iq3::element(s.grids[w],static_cast<const uint8_t*>(b.p[s.ni+s.no+w]),k);};
 auto tree=[&](int n,auto value){return ng::tree(t,n,value);};
 auto rope=[&](auto value,auto store,int width,int w,int pos){
  if(g.rotary<=0 || g.rotary%2 || 64%g.rotary || g.rotary>width || pos<0 || pos>=rope_constants::positions){t.each(1,[&](int){b.fail();});return;}
  float inv=detmath::rsqrt(tree(width,[&](int k){float v=value(k);return v*v;})/float(width)+1e-6f);t.barrier();
  t.each(width,[&](int k){t.x[k]=bf((value(k)*inv)*weight(w,k));});t.barrier();
  t.each(width,[&](int k){float v=t.x[k];if(k<g.rotary){int j=k%(g.rotary/2);auto table=static_cast<const uint16_t*>(b.p[b.tail()+4]);float c=rope_constants::cos(table,pos,j*64/g.rotary),z=rope_constants::sin(table,pos,j*64/g.rotary);v=k<g.rotary/2?t.x[j]*c-t.x[j+g.rotary/2]*z:t.x[j+g.rotary/2]*c+t.x[j]*z;}store(k,v);});t.barrier();
 };
 if(s.op==Op::gdn){
  int h=group/g.d,j=group%g.d,key=s.packed_heads?h%g.kh:h/(g.vh/g.kh),qb=key*g.d,kb=qb+g.kh*g.d;
  float qn=detmath::sqrt(tree(g.d,[&](int k){float x=b.in(0).get(qb+k);return x*x;})+1e-6f);t.barrier();
  float kn=detmath::sqrt(tree(g.d,[&](int k){float x=b.in(0).get(kb+k);return x*x;})+1e-6f);t.barrier();
  float gate=b.in(1).get(h)+weight(1,h),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,decay=detmath::exp(weight(0,h)*sp);int base=(h*g.d+j)*g.d;
  float pred=tree(g.d,[&](int k){return (b.in(3).get(base+k)*decay)*(b.in(0).get(kb+k)/kn);});t.barrier();
  float delta=(b.in(0).get(2*g.kh*g.d+h*g.d+j)-pred)*ng::sigmoid(b.in(2).get(h));
  auto row=[&](int k){return b.in(3).get(base+k)*decay+delta*(b.in(0).get(kb+k)/kn);};
  float y=tree(g.d,[&](int k){return row(k)*((b.in(0).get(qb+k)/qn)/detmath::sqrt(float(g.d)));});t.barrier();
  t.each(1,[&](int){b.out(0).put(group,y);});t.each(g.d,[&](int k){b.out(1).put(base+k,row(k));});
 }else if(s.op==Op::gdn_norm_gate){
  int base=group*g.d;float inv=detmath::rsqrt(tree(g.d,[&](int k){float x=b.in(0).get(base+k);return x*x;})/float(g.d)+1e-6f);t.barrier();
  t.each(g.d,[&](int k){b.out(0).put(base+k,((b.in(0).get(base+k)*inv)*weight(0,k))*ng::sigmoid(b.in(1).get(base+k)));});
 }else if(s.op==Op::qsa_prepare){
  int pos=b.safe_position();if(group<g.qh){int base=group*2*g.ad;rope([&](int k){return b.in(0).get(base+k);},[&](int k,float v){b.out(0).put(group*g.ad+k,v);b.out(1).put(group*g.ad+k,b.in(0).get(base+g.ad+k));},g.ad,0,pos);}
  else if(group<g.qh+g.kvh){int h=group-g.qh;rope([&](int k){return b.in(1).get(h*g.ad+k);},[&](int k,float v){b.out(2).put(h*g.ad+k,v);},g.ad,1,pos);}
  else {int h=group-g.qh-g.kvh;rope([&](int k){return b.in(2).get(h*g.id+k);},[&](int k,float v){b.out(3).put(h*g.id+k,v);},g.id,2,pos);}
 }else if(s.op==Op::qsa_append_pool){
  int pos=b.safe_position(),pools=(g.context+3)/4;
  if(group==pools){t.each(g.kvh*g.ad,[&](int k){b.out(0).put(pos*g.kvh*g.ad+k,b.in(0).get(k));b.out(1).put(pos*g.kvh*g.ad+k,b.in(1).get(k));});t.each(g.id,[&](int k){b.out(2).put(pos*g.id+k,b.in(2).get(k));});}
  else if(group==(pos/4)&&(pos+1)%4==0){auto pooled=[&](int k){float x=0;for(int j=0;j<4;++j){int r=group*4+j;x=x+(r<pos?b.out(2).get(r*g.id+k):b.in(2).get(k));}return bf(x/4.f);};rope(pooled,[&](int k,float v){b.out(3).put(group*g.id+k,v);},g.id,0,group*4);}
 }else if(s.op==Op::qsa_select){
  int pos=b.safe_position(),n=(pos+1)/4,base=2*((g.context+3)/4);
  for(int h=0;h<g.ih;++h)for(int block=0;block<n;++block){float score=ng::tree(t,g.id,[&](int k){return b.in(0).get(h*g.id+k)*b.in(1).get(block*g.id+k);},base);t.barrier();t.each(1,[&](int){t.x[block]=(h?t.x[block]:0.f)+std::max(0.f,score);});t.barrier();}
  t.each(n,[&](int k){t.x[k]=t.x[k]/detmath::sqrt(float(g.id));});t.barrier();int count=std::min(n,g.budget/4);
  bool finite=true;for(int j=0;j<n;++j)finite=finite&&std::isfinite(t.x[j]);
  if(!finite){t.each(g.budget+3,[&](int j){b.out(0).put(j,-1);});t.each(1,[&](int){b.fail();});return;}
  t.each(g.budget+3,[&](int j){b.out(0).put(j,-1);});t.barrier();t.each(n,[&](int block){int rank=0;for(int k=0;k<n;++k)rank+=t.x[k]>t.x[block]||(t.x[k]==t.x[block]&&k<block);if(rank<count)for(int j=0;j<4;++j)b.out(0).put(rank*4+j,block*4+j);});
  t.each(pos+1-n*4,[&](int j){b.out(0).put(count*4+j,n*4+j);});
 }else if(s.op==Op::qsa_attention){
  int h=group,kh=h/(g.qh/g.kvh),n=0,pos=b.safe_position();
  while(n<int(b.in(4).n)) {float value=b.in(4).get(n);if(value==-1)break;
   // Validate before any int conversion, including a NaN sentinel.
   (void)b.safe_id(value,g.context,pos);++n;}
  int base=g.budget+3;
  if(!n){t.each(1,[&](int){b.fail();});return;}
  for(int j=0;j<n;++j){int id=b.safe_id(b.in(4).get(j),g.context,pos);float score=ng::tree(t,g.ad,[&](int k){return b.in(2).get((id*g.kvh+kh)*g.ad+k)*b.in(0).get(h*g.ad+k);},base)/detmath::sqrt(float(g.ad));t.barrier();t.each(1,[&](int){t.x[j]=score;});t.barrier();}
  float maximum=-INFINITY;for(int j=0;j<n;++j)maximum=std::max(maximum,t.x[j]);t.each(n,[&](int j){t.x[j]=detmath::exp(t.x[j]-maximum);t.x[base+j]=t.x[j];});t.barrier();float den=t.sum(n,base);t.barrier();t.each(n,[&](int j){t.x[j]=t.x[j]/den;});t.barrier();
  for(int k=0;k<g.ad;++k){float value=ng::tree(t,n,[&](int j){int id=b.safe_id(b.in(4).get(j),g.context,pos);return t.x[j]*b.in(3).get((id*g.kvh+kh)*g.ad+k);},base);t.barrier();t.each(1,[&](int){b.out(0).put(h*g.ad+k,bf(value)*ng::sigmoid(b.in(1).get(h*g.ad+k)));});t.barrier();}
 }
}
int tiny_groups(const Spec& s){switch(s.op){case Op::gdn:return s.g.vh*s.g.d;case Op::gdn_norm_gate:return s.g.vh;case Op::qsa_prepare:return s.g.qh+s.g.kvh+s.g.ih;case Op::qsa_append_pool:return (s.g.context+3)/4+1;case Op::qsa_attention:return s.g.qh;default:return 1;}}
// Remaining integration sites are direct data-parallel translations of Core.
// Reduction order is the same adjacent binary tree, including odd zero padding.
template<class Team> void simple(Bound b,int group,Team t) {
 auto s=b.s;auto bf=[](float x){return ng::Args::bf(x);};
 t.each(1,[&](int){t.x[0]=float(!*b.active());});t.barrier();
 if(t.x[0])return;t.barrier();
 if(s.special==Special::begin){t.each(1,[&](int){if(*b.position()>=unsigned(s.g.context))b.fail();});return;}
 t.each(1,[&](int){t.x[0]=float(b.failed());});t.barrier();
 if(t.x[0])return;t.barrier();
 if(s.special==Special::commit){t.each(1,[&](int){++*b.position();});return;}
 if(s.special==Special::broadcast){t.each(int(b.out(0).n),[&](int j){b.out(0).put(j,b.in(0).get(j%b.in(0).n));});return;}
 if(s.special==Special::check_status){
  float failed=ng::tree(t,int(b.in(0).n),[&](int j){return float(b.in(0).get(j)!=0);});t.barrier();
  t.each(1,[&](int){if(failed)b.fail();});return;
 }
 if(s.special==Special::ple_hash){t.each(1,[&](int){
  auto history=static_cast<int64_t*>(b.in(1).p),meta=static_cast<int64_t*>(b.in(2).p),ids=static_cast<int64_t*>(b.out(0).p);
  int64_t token=static_cast<int32_t*>(b.in(0).p)[0],old0=history[0],old1=history[1];if(old1==s.g.eos)old0=s.g.eos;
  for(int n=2;n<=3;++n){uint64_t hash=uint64_t(token)*uint64_t(meta[0]);hash^=uint64_t(old1)*uint64_t(meta[1]);if(n==3)hash^=uint64_t(old0)*uint64_t(meta[2]);auto v=std::bit_cast<int64_t>(hash);
   for(int h=0;h<8;++h){int j=(n-2)*8+h;auto size=meta[3+j];if(size<=0){b.fail();return;}ids[j]=(v%size+size)%size+meta[19+j];}}
  history[0]=old1;history[1]=token;
 });return;}
 if(s.op==Op::hc_combine){t.each(int(b.out(0).n),[&](int j){b.out(0).put(j,b.in(0).get(j)+b.in(1).get(j%s.site.shape[1])*(2.f*ng::sigmoid(b.in(2).get(j/s.site.shape[1])/4.f)));});}
 else if(s.op==Op::expert_gather){
  t.each(s.g.top,[&](int j){float value=b.in(0).get(j);
   bool valid=std::isfinite(value)&&value>=0&&value<float(s.g.experts)&&std::floor(value)==value;
   int id=valid?int(value):0;t.x[j]=valid?0:1;
   for(int k=0;k<3;++k){b.out(0).put(j*3+k,k==0?id:k==1?0:s.g.mid);b.out(1).put(j*3+k,k==0?id:k==1?0:s.g.h);}});t.barrier();
  float bad=t.sum(s.g.top);t.barrier();t.each(1,[&](int){if(bad)b.fail();});
  // Even invalid routes have initialized, in-range downstream inputs.
  t.each(int(b.out(2).n),[&](int j){b.out(2).put(j,b.in(1).get(j%b.in(1).n));});
 }else if(s.op==Op::route){
  int n=int(b.in(0).n),top=s.site.shape[1];float maximum=-INFINITY;bool finite=true;
  for(int j=0;j<n;++j){float v=b.in(0).get(j);finite=finite&&std::isfinite(v);maximum=std::max(maximum,v);}
  if(!finite){t.each(1,[&](int){b.fail();});return;}
  t.each(n,[&](int j){t.x[j]=detmath::exp(b.in(0).get(j)-maximum);t.x[n+j]=t.x[j];});t.barrier();float den=t.sum(n);t.barrier();
  t.each(n,[&](int j){t.x[n+j]=t.x[n+j]/den;});t.barrier();
  t.each(n,[&](int j){int rank=0;float v=t.x[n+j];for(int k=0;k<n;++k)rank+=t.x[n+k]>v||(t.x[n+k]==v&&k<j);if(rank<top){b.out(0).put(rank,j);t.x[2*n+rank]=v;t.x[2*n+top+rank]=v;}});t.barrier();
  float selected=t.sum(top,2*n);t.barrier();t.each(top,[&](int j){b.out(1).put(j,t.x[2*n+top+j]/selected);});
 }else if(s.op==Op::ple_gate){
  int width=s.g.h;float sum=ng::tree(t,width,[&](int k){return bf(b.in(0).get(group*width+k)*b.in(1).get(group*width+k));});t.barrier();
  float z=bf(bf(sum)/detmath::sqrt(float(width))),root=bf(detmath::sqrt(std::max(std::abs(z),1e-6f))),sign=z>0?1.f:z<0?-1.f:0.f,gate=bf(ng::sigmoid(bf(sign*root)));
  t.each(width,[&](int k){b.out(0).put(group*width+k,gate*b.in(2).get(k));});
 }else if(s.op==Op::ple_add){t.each(int(b.out(0).n),[&](int j){b.out(0).put(j,b.in(0).get(j)+bf(b.in(1).get(j)+b.in(2).get(j)));});}
 else if(s.op==Op::argmax){
  t.each(128,[&](int lane){int best=lane;bool finite=true;for(int j=lane;j<int(b.in(0).n);j+=128){float v=b.in(0).get(j);finite=finite&&std::isfinite(v);if(v>b.in(0).get(best))best=j;}t.x[lane]=lane<int(b.in(0).n)?float(best):-1.f;t.x[128+lane]=float(finite);});t.barrier();
  t.each(1,[&](int){int best=0;bool finite=true;for(int lane=0;lane<128;++lane){int j=int(t.x[lane]);finite=finite&&bool(t.x[128+lane]);if(j>=0&&(b.in(0).get(j)>b.in(0).get(best)||(b.in(0).get(j)==b.in(0).get(best)&&j<best)))best=j;}b.out(0).put(0,best);if(!finite)b.fail();});
 }
}
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

#ifdef OWN_RT_HOST_ONLY
template<Op Code,int Phase,int FixedN=0,int FixedTop=0> struct SimpleNew final:HostOperation {
 Spec spec;int work;SimpleNew(Spec s,int n):spec(s),work(n){}
 void run(std::span<void*const> p)const override{Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());packet24::mock_items(work,[&](size_t i){simple_body<Code,Phase,FixedN,FixedTop>(b,int(i));});}
};
#else
template<Op Code,int Phase,int FixedN=0,int FixedTop=0> struct SimpleNew final:ownrt::SyclOperation {
 Spec spec;int work;SimpleNew(Spec s,int n):spec(s),work(n){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());int n=work;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(n),[=](sycl::id<1> i){simple_body<Code,Phase,FixedN,FixedTop>(b,int(i[0]));});});
 }
};
#endif
template<Op Code,int FixedN=0,int FixedTop=0> Launch simple_new_submit(ownrt::Device& d,const Spec& s,std::span<const ownrt::Allocation> bindings,std::span<const ownrt::Event> deps){
 Launch result{};auto issue=[&]<int Phase>(){SimpleNew<Code,Phase,FixedN,FixedTop> op(s,simple_work(s,Phase));std::array<ownrt::Event,1> after{result.last};auto e=d.compute(op,bindings,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;};
 issue.template operator()<0>();if constexpr(Code==Op::route||Code==Op::argmax||Code==Op::expert_gather)issue.template operator()<1>();
 if constexpr(Code==Op::route){issue.template operator()<2>();issue.template operator()<3>();issue.template operator()<4>();}return result;
}

#ifdef OWN_RT_HOST_ONLY
struct NgHost final:HostOperation{ng::Shape shape;explicit NgHost(ng::Shape s):shape(s){}void run(std::span<void*const> p)const override{ng::Args a;std::copy(p.begin(),p.end(),a.p.begin());ng::cpu(shape,a);}};
struct Glue final:HostOperation {
 Spec s;int mode;Glue(Spec v,int m):s(v),mode(m){}
 void run(std::span<void*const> p)const override{
  Bound b{s,{}};std::copy(p.begin(),p.end(),b.p.begin());auto ctrl=static_cast<int32_t*>(p.back());
  if(mode==1){ctrl[0]=*b.position();ctrl[1]=*b.active();ctrl[2]=b.failed();}
  else if(mode==2){if(ctrl[2])b.fail();}
  else if(mode==3){std::vector<float> scratch(std::max(8192,s.g.h));for(int g=0;g<tiny_groups(s);++g)tiny(b,g,ng::HostTeam{scratch.data()});}
  else {std::vector<float> scratch(std::max(4096,s.g.h));int groups=s.special==Special::normal&&s.op==Op::ple_gate?4:1;for(int g=0;g<groups;++g)simple(b,g,ng::HostTeam{scratch.data()});}
 }
};
#else
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=it.get_local_range(0))f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
struct Glue final:ownrt::SyclOperation {
 Spec s;int mode;Glue(Spec v,int m):s(v),mode(m){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  Bound b{s,{}};std::copy(p.begin(),p.end(),b.p.begin());auto ctrl=static_cast<int32_t*>(p.back());auto mode_=mode;
  if(mode==1||mode==2)return q.submit([&](sycl::handler& h){h.depends_on(deps);h.single_task([=]{if(mode_==1){ctrl[0]=*b.position();ctrl[1]=*b.active();ctrl[2]=b.failed();}else if(mode_==2){if(ctrl[2])b.fail();}});});
  int groups=mode==3?tiny_groups(s):s.special==Special::normal&&s.op==Op::ple_gate?4:1,local=std::max(8192,s.g.h);
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> scratch(local,h);h.parallel_for(sycl::nd_range<1>(groups*128,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto t=Team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()};if(mode_==3)tiny(b,it.get_group_linear_id(),t);else simple(b,it.get_group_linear_id(),t);});});
 }
};
#endif
}
Launch submit_parallel(ownrt::Device& d,const Spec& s,std::span<const ownrt::Allocation> bindings,ownrt::Allocation control,ownrt::Allocation score,ownrt::Allocation probability,std::span<const ownrt::Event> deps){
 if(bindings.size()!=size_t(s.ni+s.no+s.nw+5)||bindings.size()>31)throw std::invalid_argument("adapter binding count");
 if(s.implementation==2&&s.special==Special::normal&&(s.op==Op::route||s.op==Op::argmax))return round2::submit_simple(d,s,bindings,deps);
 if(s.implementation&&s.special==Special::broadcast)return simple_new_submit<Op::hc_mix>(d,s,bindings,deps);
 if(s.implementation&&s.special==Special::normal){switch(s.op){
 case Op::route:if(s.sizes[0]==512&&s.site.shape[1]==10)return simple_new_submit<Op::route,512,10>(d,s,bindings,deps);return simple_new_submit<Op::route>(d,s,bindings,deps);
 case Op::expert_gather:return simple_new_submit<Op::expert_gather>(d,s,bindings,deps);
 case Op::hc_combine:if(!s.fused_combine_norm)return simple_new_submit<Op::hc_combine>(d,s,bindings,deps);break;
 case Op::argmax:return simple_new_submit<Op::argmax>(d,s,bindings,deps);
 case Op::ple_add:return simple_new_submit<Op::ple_add>(d,s,bindings,deps);
 default:break;}}
 ng::Shape shape{};shape.capacity=s.g.context;shape.budget=s.g.budget;
 std::array<ownrt::Allocation,19> a;a.fill(control);a[15]=bindings[s.ni+s.no+s.nw+1];a[16]=bindings.back();a[17]=bindings[s.ni+s.no+s.nw+2];a[18]=bindings[s.ni+s.no+s.nw+3];
 auto in=[&](int dst,int j){a[dst]=bindings[j];};auto out=[&](int dst,int j){a[dst]=bindings[s.ni+j];};auto weight=[&](int dst,int j){a[dst]=bindings[s.ni+s.no+j];};
 bool use_ng=s.special==Special::normal;
 if(s.nw){bool gdn=s.special==Special::normal&&s.op==Op::gdn;bool f32=s.grids[gdn?1:0]==iq3::Type::F32;for(int j=0;j<s.nw;++j)if((s.grids[j]==iq3::Type::F32)!=f32&&!(gdn&&j==0))throw std::invalid_argument("mixed non-GEMV gain encodings");if(gdn&&s.grids[0]!=iq3::Type::F32)throw std::invalid_argument("stored GDN decay must be F32");if(f32)shape.flags|=8;}
 if(s.fused_combine_norm){
  shape.op=ng::combine_norm;shape.width=s.site.shape[1];shape.heads=int(s.sizes[0])/shape.width;shape.flags|=s.site.parameter?1:0;
  in(0,0);in(1,1);in(2,2);weight(3,0);out(4,0);out(5,1);
 }else if(use_ng)switch(s.op){
 case Op::norm:shape.op=ng::norm;shape.width=s.site.shape[1];shape.heads=int(s.sizes[0])/shape.width;shape.flags|=s.site.parameter?1:0;in(0,0);weight(1,0);out(2,0);break;
 case Op::silu_div4:case Op::silu_product:shape.op=ng::activation;shape.width=int(s.sizes[0]);shape.extra=s.op==Op::silu_product;in(0,0);if(shape.extra)in(1,1);out(2,0);break;
 case Op::hc_mix:shape.op=ng::mix;shape.width=s.site.shape[1];in(0,0);in(1,1);out(2,0);break;
 case Op::conv:shape.op=ng::conv;shape.width=s.site.shape[0];shape.extra=s.site.parameter;in(0,0);in(1,1);weight(2,0);out(3,0);out(4,1);break;
 case Op::gdn:shape.op=ng::gdn;shape.flags|=2|(s.packed_heads?4:0);in(0,0);in(1,1);in(2,2);weight(3,0);weight(4,1);in(5,3);out(6,0);out(7,1);break;
 case Op::gdn_norm_gate:shape.op=ng::gated_norm;shape.heads=48;in(0,0);in(1,1);weight(2,0);out(3,0);break;
 case Op::moe_combine:shape.op=ng::moe_combine;shape.width=s.site.shape[1];shape.extra=s.site.shape[0];in(0,0);in(1,1);in(2,2);in(3,3);out(4,0);break;
 case Op::qsa_prepare:shape.op=ng::prepare;for(int j=0;j<3;++j){in(j,j);weight(3+j,j);}for(int j=0;j<4;++j)out(6+j,j);break;
 case Op::qsa_append_pool:shape.op=ng::pool;for(int j=0;j<3;++j)in(j,j);weight(3,0);for(int j=0;j<4;++j)out(4+j,j);break;
 case Op::qsa_select:shape.op=ng::select;in(0,0);in(1,1);out(2,0);break;
 case Op::qsa_attention:shape.op=ng::attention_score;for(int j=0;j<5;++j)in(j,j);out(5,0);a[6]=score;a[7]=probability;break;
 default:use_ng=false;
 }
 // Packet15's GDN/QSA geometry is fixed to the real model. Mini's synthetic
 // geometry uses dimensioned parallel equations, never the interpreter control.
 bool tiny=s.g.h!=2560;
 bool tiny_core=tiny&&s.special==Special::normal&&(s.op==Op::gdn||s.op==Op::gdn_norm_gate||s.op==Op::qsa_prepare||s.op==Op::qsa_append_pool||s.op==Op::qsa_select||s.op==Op::qsa_attention);
 std::array<ownrt::Allocation,32> b{};std::copy(bindings.begin(),bindings.end(),b.begin());b[bindings.size()]=control;
 if(!use_ng||tiny_core){Glue k(s,tiny_core?3:0);auto e=d.compute(k,std::span<const ownrt::Allocation>(b.data(),bindings.size()+1),deps);return {e,e,1};}
 // Validate before submitting anything, so a bad shape cannot strand a partial chain.
 ng::validate(shape);auto required=ng::required_bytes(shape);for(int j=0;j<19;++j)if(d.arena.row(a[j]).bytes<required[j])throw std::invalid_argument("adapter allocation too short at slot "+std::to_string(j));
 ownrt::Event first=0,last=0;uint32_t count=0;
 auto kernel=[&](ng::Shape sh){std::array<ownrt::Event,1> after{last};auto chain=last?std::span<const ownrt::Event>(after):deps;
  if(s.implementation==3&&(sh.op==ng::attention_score||sh.op==ng::attention_softmax||sh.op==ng::attention_value)){auto e=p33r2::submit(d,sh,a,bindings[s.ni+s.no+s.nw],chain);last=e.last;if(!first)first=e.first;count+=e.passes;return;}
  if(s.implementation==2&&round2::supported(sh)){auto e=round2::submit(d,sh,a,bindings[s.ni+s.no+s.nw],chain);last=e.last;if(!first)first=e.first;count+=e.passes;return;}
  if(s.implementation&&specialised::supported(sh)){auto e=specialised::submit(d,sh,a,bindings[s.ni+s.no+s.nw],chain);last=e.last;if(!first)first=e.first;count+=e.passes;return;}
#ifdef OWN_RT_HOST_ONLY
  NgHost k(sh);last=d.compute(k,a,chain);
#else
  last=ng::submit(d,sh,a,chain);
#endif
  if(!first)first=last;++count;};
 if(s.implementation>=4&&shape.op==ng::attention_score){auto e=p30integrated::attention(d,shape,a,unsigned(s.implementation-4),deps);return e;}
 kernel(shape);if(shape.op==ng::attention_score){shape.op=ng::attention_softmax;kernel(shape);shape.op=ng::attention_value;kernel(shape);}
 return {first,last,count};
}
}
