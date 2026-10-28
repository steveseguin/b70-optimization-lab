#include "reference_sort_workspace.hpp"
#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/p30_submit.hpp"
#include "stage2/packet194-expert-diet-engine/p49_qsa_submit.hpp"
#include "stage2/packet194-expert-diet-engine/adapter.hpp"
#include "stage2/packet194-expert-diet-engine/route42.hpp"
#include "stage2/packet194-expert-diet-engine/p42_submit.hpp"
#include "stage2/packet194-expert-diet-engine/kernels.hpp"
#include "gsq-rco-iq3s/recurrent-f32/recurrent_policy.hpp"
#include "stage2/packet194-expert-diet-engine/specialised_submit.hpp"
#include "stage2/packet194-expert-diet-engine/experts_v2.hpp"
#include "stage2/packet194-expert-diet-engine/round2_submit.hpp"
#include "stage2/packet194-expert-diet-engine/p33r2.hpp"
#include "stage2/packet194-expert-diet-engine/mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/native.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace packet18 {
using namespace integrated;
namespace {
struct Bound {
 Spec s;std::array<void*,32> p;
 View in(int j)const{return {p[j],s.sizes[j],s.types[j]};}
 View out(int j)const{int k=s.ni+j;return {p[k],s.sizes[k],s.types[k]};}
 int tail()const{return s.ni+s.no+s.nw;}
 void* scratch()const{return p[tail()];}
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
 const auto s=b.s;const auto g=s.g;const bool exact=s.f32_activations;
 // Snapshot the guard once per workgroup so another group's fail cannot make
 // lanes diverge around a barrier. The error itself is atomic across groups.
 t.each(1,[&](int){t.x[0]=float(!*b.active()||b.failed());});t.barrier();
 if(t.x[0])return;t.barrier();
 if(s.extent&&(s.op==Op::qsa_select||s.op==Op::qsa_attention)&&*b.position()>=unsigned(s.extent)){t.each(1,[&](int){b.fail();});return;}
 auto bf=[exact](float x){return exact?x:ng::Args::bf(x);};
 auto weight=[&](int w,int k){return iq3::element(s.grids[w],static_cast<const uint8_t*>(b.p[s.ni+s.no+w]),k);};
 auto tree=[&](int n,auto value){return ng::tree(t,n,value);};
 auto rope=[&](auto value,auto store,int width,int w,int pos){
  if(g.rotary<=0 || g.rotary%2 || 64%g.rotary || g.rotary>width || pos<0 || pos>=rope_constants::positions){t.each(1,[&](int){b.fail();});return;}
  float inv=detmath::rsqrt(tree(width,[&](int k){float v=value(k);return v*v;})/float(width)+1e-6f);t.barrier();
  t.each(width,[&](int k){t.x[k]=bf((value(k)*inv)*weight(w,k));});t.barrier();
  t.each(width,[&](int k){float v=t.x[k];if(k<g.rotary){int j=k%(g.rotary/2);float c,z;if(exact){auto table=static_cast<const float*>(b.p[b.tail()+4]);c=rope_constants::cos(table,pos,j*64/g.rotary);z=rope_constants::sin(table,pos,j*64/g.rotary);}else{auto table=static_cast<const uint16_t*>(b.p[b.tail()+4]);c=rope_constants::cos(table,pos,j*64/g.rotary);z=rope_constants::sin(table,pos,j*64/g.rotary);}v=k<g.rotary/2?t.x[j]*c-t.x[j+g.rotary/2]*z:t.x[j+g.rotary/2]*c+t.x[j]*z;}store(k,v);});t.barrier();
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
  int pos=b.safe_position(),pools=1;
  if(group==pools){t.each(g.kvh*g.ad,[&](int k){b.out(0).put(pos*g.kvh*g.ad+k,b.in(0).get(k));b.out(1).put(pos*g.kvh*g.ad+k,b.in(1).get(k));});t.each(g.id,[&](int k){b.out(2).put(pos*g.id+k,b.in(2).get(k));});}
  else if(group==0&&(pos+1)%4==0){group=pos/4;auto pooled=[&](int k){float x=0;for(int j=0;j<4;++j){int r=group*4+j;x=x+(r<pos?b.out(2).get(r*g.id+k):b.in(2).get(k));}return bf(x/4.f);};rope(pooled,[&](int k,float v){b.out(3).put(group*g.id+k,v);},g.id,0,group*4);}
 }else if(s.op==Op::qsa_select){
  int pos=b.safe_position(),n=(pos+1)/4,base=((s.extent?s.extent:g.context)+3)/4;
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
int tiny_groups(const Spec& s){switch(s.op){case Op::gdn:return s.g.vh*s.g.d;case Op::gdn_norm_gate:return s.g.vh;case Op::qsa_prepare:return s.g.qh+s.g.kvh+s.g.ih;case Op::qsa_append_pool:return 2;case Op::qsa_attention:return s.g.qh;default:return 1;}}
inline int tiny_local_floats(const Spec& s){return std::max(std::max(8192,s.g.h),s.op==Op::qsa_select?((s.extent?s.extent:s.g.context)+3)/4+s.g.id:0);}
// Remaining integration sites are direct data-parallel translations of Core.
// Reduction order is the same adjacent binary tree, including odd zero padding.
template<class Team> void simple(Bound b,int group,Team t) {
 auto s=b.s;auto bf=[exact=s.f32_activations](float x){return exact?x:ng::Args::bf(x);};
 t.each(1,[&](int){t.x[0]=float(!*b.active());});t.barrier();
 if(t.x[0])return;t.barrier();
 if(s.special==Special::begin){t.each(1,[&](int){if(*b.position()>=unsigned(s.g.context))b.fail();});return;}
 t.each(1,[&](int){t.x[0]=float(b.failed());});t.barrier();
 if(t.x[0])return;t.barrier();
 if(s.special==Special::commit){t.each(1,[&](int){++*b.position();});return;}
 if(s.special==Special::broadcast){t.each(int(b.out(0).n),[&](int j){b.out(0).put(j,b.in(0).get(j%b.in(0).n));});return;}
 if(s.special==Special::check_status){
  // Any nonzero slot status in any status input (inputs: statuses, then error and active). A merged check over a
  // layer's expert gate/up/down statuses sets the error exactly when one of the separate checks would.
  float failed=0;for(int k=0;k+2<s.ni;++k){failed=failed+ng::tree(t,int(b.in(k).n),[&](int j){return float(b.in(k).get(j)!=0);});t.barrier();}
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
  t.each(n,[&](int j){int rank=0;float v=t.x[n+j];for(int k=0;k<n;++k)rank+=t.x[n+k]>v||(t.x[n+k]==v&&k<j);if(rank<top){b.out(0).put(rank,j);t.x[2*n+rank]=v;t.x[2*n+top+rank]=v;
   // The folded route ABI also owns the gather descriptors. Preserve the
   // two-output reference arithmetic and emit the unfused gather's layout.
   if(s.no>=4)for(int k=0;k<3;++k){b.out(2).put(rank*3+k,k==0?j:k==1?0:s.g.mid);b.out(3).put(rank*3+k,k==0?j:k==1?0:s.g.h);}
  }});t.barrier();
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
// One token row of a multi-row SimpleNew launch: row-major bindings and the temporary are offset by `row` in the
// accessors only, so the body below is unchanged and nothing large is copied per work item.
struct RowBound {
 const Bound& b;int row;const Spec& s;
 View in(int j)const{View v=b.in(j);if(s.row_bytes[j])v.p=static_cast<unsigned char*>(v.p)+size_t(row)*s.row_bytes[j];return v;}
 View out(int j)const{View v=b.out(j);if(s.row_bytes[s.ni+j])v.p=static_cast<unsigned char*>(v.p)+size_t(row)*s.row_bytes[s.ni+j];return v;}
 void* scratch()const{return static_cast<unsigned char*>(b.scratch())+size_t(row)*s.tmp_row_bytes;}
 uint32_t* active()const{return b.active();}
 uint32_t failed()const{return b.failed();}
 void fail()const{b.fail();}
};
template<Op Code,int Phase,int FixedN=0,int FixedTop=0,class B=Bound> void simple_body(B b,int index){
 constexpr int phase=Phase;constexpr bool raw_rank=false;
 if(!*b.active()||b.failed())return;
 const auto& s=b.s;float* tmp=static_cast<float*>(b.scratch());
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
 else if constexpr(Code==Op::ple_add){float v=b.in(1).get(index)+b.in(2).get(index);b.out(0).put(index,b.in(0).get(index)+(s.f32_activations?v:ng::Args::bf(v)));}
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
 void run(std::span<void*const> p)const override{Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());
  if(spec.tokens==1){packet24::mock_items(work,[&](size_t i){simple_body<Code,Phase,FixedN,FixedTop>(b,int(i));});return;}
  for(int r=0;r<spec.tokens;++r)packet24::mock_items(work,[&](size_t i){simple_body<Code,Phase,FixedN,FixedTop>(RowBound{b,r,b.s},int(i));});}
};
#else
template<Op Code,int Phase,int FixedN=0,int FixedTop=0> struct SimpleNew final:ownrt::SyclOperation {
 Spec spec;int work;SimpleNew(Spec s,int n):spec(s),work(n){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());int n=work;
  if(spec.tokens>1) {
   // Token rows: one launch for every row of this phase. Row r runs the unchanged single-row body on its own row of
   // each row-major binding and its own slice of the temporary; shared bindings stay shared.
   const int per=n,total=n*spec.tokens;
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(total)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> i){
    const int r=int(i[0])/per,index=int(i[0])%per;
    simple_body<Code,Phase,FixedN,FixedTop>(RowBound{b,r,b.s},index);}));});
  }
  if(spec.implementation==11)return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(((n+31)/32)*32,32)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> i)[[sycl::reqd_sub_group_size(32)]]{int j=i.get_global_linear_id();if(j<n)simple_body<Code,Phase,FixedN,FixedTop>(b,j);}));});
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(n)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> i){simple_body<Code,Phase,FixedN,FixedTop>(b,int(i[0]));}));});
 }
};
#endif
#ifndef OWN_RT_HOST_ONLY
// Route in one launch: one work-group per row runs the unchanged five route phases of simple_body in order, with a
// work-group barrier (global and local fence) where the five-launch form had kernel boundaries. Every value is computed
// by the same code from the same inputs. Exact but neutral on SC117 decode (27.67 vs 28.00 tok/s, 2026-10-24), so
// opt-in: OWNRT_ROUTE_GROUP=1.
template<int FixedN,int FixedTop> struct RouteGroup final:ownrt::SyclOperation {
 static constexpr int Local=512;
 Spec spec;explicit RouteGroup(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());
  const std::array<int,5> work{simple_work(spec,0),simple_work(spec,1),simple_work(spec,2),simple_work(spec,3),simple_work(spec,4)};
  const int rows=spec.tokens;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(rows)*Local,Local)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it){
   const int r=int(it.get_group_linear_id()),lid=int(it.get_local_linear_id());
   auto phase=[&]<int Phase>(){
    for(int i=lid;i<work[Phase];i+=Local){if(rows>1)simple_body<Op::route,Phase,FixedN,FixedTop>(RowBound{b,r,b.s},i);else simple_body<Op::route,Phase,FixedN,FixedTop>(b,i);}
    it.barrier(sycl::access::fence_space::global_and_local);};
   phase.template operator()<0>();phase.template operator()<1>();phase.template operator()<2>();phase.template operator()<3>();phase.template operator()<4>();
  }));});
 }
};
// Route, fast and exact: one work-group per row. The softmax is the five-phase form's (same max, the same exp, the same
// subtree<16> chunk sums and subtree<256> denominator, the same division). The top ten come from ten work-group
// maxima of an integer key (probability bits, then the lower expert id), which is exactly the five-phase rank order
// (larger probability first, ties to the lower id). The selected probabilities are normalised by the same
// subtree<32>. OWNRT_ROUTE_FAST=0 keeps the five-phase form.
template<int N,int Top> struct RouteFast final:ownrt::SyclOperation {
 Spec spec;explicit RouteFast(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());const int rows=spec.tokens;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(rows)*N,N)](sycl::handler& h){
   sycl::local_accessor<float,1> ex(N,h),prob(N,h),sums(N/16,h);sycl::local_accessor<int,1> bad(1,h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it){
    const int r=int(it.get_group_linear_id()),j=int(it.get_local_linear_id());const RowBound rb{b,r,b.s};auto g=it.get_group();
    if(!*rb.active()||rb.failed())return; // uniform across the work-group
    if(j==0)bad[0]=0;it.barrier(sycl::access::fence_space::local_space);
    const float x=rb.in(0).get(j);if(!std::isfinite(x))sycl::atomic_ref<int,sycl::memory_order::relaxed,sycl::memory_scope::work_group,sycl::access::address_space::local_space>(bad[0]).store(1);
    it.barrier(sycl::access::fence_space::local_space);
    if(bad[0]){if(j==0)rb.fail();return;}
    const float maximum=sycl::reduce_over_group(g,x,sycl::maximum<float>());
    ex[j]=detmath::exp(x-maximum);it.barrier(sycl::access::fence_space::local_space);
    constexpr int chunks=(N+15)/16;
    if(j<chunks)sums[j]=subtree<16>(N,j*16,[&](int i){return ex[i];});
    it.barrier(sycl::access::fence_space::local_space);
    const float den=subtree<256>(chunks,0,[&](int i){return sums[i];});
    prob[j]=ex[j]/den;it.barrier(sycl::access::fence_space::local_space);
    bool taken=false;
    for(int rank=0;rank<Top;++rank){
     // Same order as the former 64-bit key (non-negative probability bits, then the lower id), as two 32-bit
     // reductions: the largest bits among candidates, then the smallest id holding them. 64-bit integer reductions are
     // emulated on the B70.
     const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);
     const uint32_t top=sycl::reduce_over_group(g,taken?0u:bits+1u,sycl::maximum<uint32_t>());
     const int index=sycl::reduce_over_group(g,(!taken&&bits+1u==top)?j:N,sycl::minimum<int>());
     if(j==index)taken=true;
     if(j==0){const float v=prob[index];rb.out(0).put(rank,index);rb.out(1).put(rank,v);
      if(rb.s.no>=4)for(int k=0;k<3;++k){rb.out(2).put(rank*3+k,k==0?index:k==1?0:rb.s.g.mid);rb.out(3).put(rank*3+k,k==0?index:k==1?0:rb.s.g.h);}}
    }
    if(j==0){float sum=subtree<32>(Top,0,[&](int i){return rb.out(1).get(i);});for(int i=0;i<Top;++i)rb.out(1).put(i,rb.out(1).get(i)/sum);}
   }));});
 }
};
// OWNRT_EXPERTS_V2 "guard"/"route" (lab 2026-10-26): RouteFast with the active/sticky-error guard read once per
// work-group (lane 0, through the local flag word, instead of by all 512 lanes) and, with MERGE, the ten arg-max rounds
// split in two levels: each 32-lane subgroup first takes its own ten best by subgroup reductions (no work-group
// barrier), then subgroup 0 runs the ten rounds over those 160 candidates. The order is RouteFast's (larger probability
// bits, then the lower id) and every top-ten entry is in its subgroup's ten best, so the same ten ids come out in the
// same order. The softmax, the outputs and the normalisation are RouteFast's code. Microbench: 9.8 -> 8.4 us (MERGE).
template<int N,int Top,bool MERGE> struct RouteFast2 final:ownrt::SyclOperation {
 static_assert(N%32==0&&(N/32)*Top%32==0,"route geometry");
 Spec spec;explicit RouteFast2(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());const int rows=spec.tokens;
  constexpr int C=(N/32)*Top;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(rows)*N,N)](sycl::handler& h){
   sycl::local_accessor<float,1> ex(N,h),prob(N,h),sums(N/16,h);sycl::local_accessor<uint32_t,1> flags(2+(MERGE?2*C:0),h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    const int r=int(it.get_group_linear_id()),j=int(it.get_local_linear_id());const RowBound rb{b,r,b.s};auto g=it.get_group();
    uint32_t* bad=flags.get_multi_ptr<sycl::access::decorated::no>().get();
    if(j==0){bad[0]=0;bad[1]=(!*rb.active()||rb.failed())?1u:0u;}
    it.barrier(sycl::access::fence_space::local_space);
    if(bad[1])return; // uniform across the work-group
    const float x=rb.in(0).get(j);if(!std::isfinite(x))sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::work_group,sycl::access::address_space::local_space>(bad[0]).store(1);
    it.barrier(sycl::access::fence_space::local_space);
    if(bad[0]){if(j==0)rb.fail();return;}
    const float maximum=sycl::reduce_over_group(g,x,sycl::maximum<float>());
    ex[j]=detmath::exp(x-maximum);it.barrier(sycl::access::fence_space::local_space);
    constexpr int chunks=(N+15)/16;
    if(j<chunks)sums[j]=subtree<16>(N,j*16,[&](int i){return ex[i];});
    it.barrier(sycl::access::fence_space::local_space);
    const float den=subtree<256>(chunks,0,[&](int i){return sums[i];});
    prob[j]=ex[j]/den;it.barrier(sycl::access::fence_space::local_space);
    auto put=[&](int rank,int index){const float v=prob[index];rb.out(0).put(rank,index);rb.out(1).put(rank,v);
     if(rb.s.no>=4)for(int k=0;k<3;++k){rb.out(2).put(rank*3+k,k==0?index:k==1?0:rb.s.g.mid);rb.out(3).put(rank*3+k,k==0?index:k==1?0:rb.s.g.h);}};
    if constexpr(!MERGE){
     bool taken=false;
     for(int rank=0;rank<Top;++rank){
      const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);
      const uint32_t top=sycl::reduce_over_group(g,taken?0u:bits+1u,sycl::maximum<uint32_t>());
      const int index=sycl::reduce_over_group(g,(!taken&&bits+1u==top)?j:N,sycl::minimum<int>());
      if(j==index)taken=true;
      if(j==0)put(rank,index);
     }
    } else {
     uint32_t* cbits=bad+2;uint32_t* cidx=cbits+C;
     auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sgi=int(sg.get_group_linear_id());
     const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);bool taken=false;
     for(int k=0;k<Top;++k){
      const uint32_t top=sycl::reduce_over_group(sg,taken?0u:bits+1u,sycl::maximum<uint32_t>());
      const int index=sycl::reduce_over_group(sg,(!taken&&bits+1u==top)?j:N,sycl::minimum<int>());
      if(j==index){taken=true;cbits[sgi*Top+k]=bits;cidx[sgi*Top+k]=uint32_t(j);}
     }
     it.barrier(sycl::access::fence_space::local_space);
     if(sgi==0){
      constexpr int PER=C/32;uint32_t cb[PER],ci[PER];bool tk[PER];
      #pragma unroll
      for(int c=0;c<PER;++c){cb[c]=cbits[lane+32*c];ci[c]=cidx[lane+32*c];tk[c]=false;}
      for(int rank=0;rank<Top;++rank){
       uint32_t best=0;
       #pragma unroll
       for(int c=0;c<PER;++c)best=std::max(best,tk[c]?0u:cb[c]+1u);
       const uint32_t top=sycl::reduce_over_group(sg,best,sycl::maximum<uint32_t>());
       uint32_t mi=uint32_t(N);
       #pragma unroll
       for(int c=0;c<PER;++c)if(!tk[c]&&cb[c]+1u==top)mi=std::min(mi,ci[c]);
       const uint32_t index=sycl::reduce_over_group(sg,mi,sycl::minimum<uint32_t>());
       #pragma unroll
       for(int c=0;c<PER;++c)if(ci[c]==index)tk[c]=true;
       if(lane==0)put(rank,int(index));
      }
     }
    }
    if(j==0){float sum=subtree<32>(Top,0,[&](int i){return rb.out(1).get(i);});for(int i=0;i<Top;++i)rb.out(1).put(i,rb.out(1).get(i)/sum);}
   }));});
 }
};
template<int N,int Top,bool MERGE> struct RouteReferenceTie2 final:ownrt::SyclOperation {
 static_assert(N%32==0&&(N/32)*Top%32==0,"route geometry");
 Spec spec;explicit RouteReferenceTie2(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  if(!spec.f32_activations||(spec.no!=2&&spec.no!=4))throw std::invalid_argument("reference tie route requires F32 and known output geometry");
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());const int rows=spec.tokens;
  constexpr int C=(N/32)*Top;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(rows)*N,N)](sycl::handler& h){
   sycl::local_accessor<int,1> selected(Top,h),reference_indices(N,h);
   sycl::local_accessor<router_reference_sort::Frame,1> reference_frames(router_reference_sort::maximum_depth,h);
   sycl::local_accessor<float,1> ex(N,h),prob(N,h),sums(N/16,h);sycl::local_accessor<uint32_t,1> flags(2+(MERGE?2*C:0),h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    const int r=int(it.get_group_linear_id()),j=int(it.get_local_linear_id());const RowBound rb{b,r,b.s};auto g=it.get_group();
    uint32_t* bad=flags.get_multi_ptr<sycl::access::decorated::no>().get();
    if(j==0){bad[0]=0;bad[1]=(!*rb.active()||rb.failed())?1u:0u;}
    it.barrier(sycl::access::fence_space::local_space);
    if(bad[1])return; // uniform across the work-group
    const float x=rb.in(0).get(j);if(!std::isfinite(x))sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::work_group,sycl::access::address_space::local_space>(bad[0]).store(1);
    it.barrier(sycl::access::fence_space::local_space);
    if(bad[0]){if(j==0)rb.fail();return;}
    const float maximum=sycl::reduce_over_group(g,x,sycl::maximum<float>());
    ex[j]=detmath::exp(x-maximum);it.barrier(sycl::access::fence_space::local_space);
    constexpr int chunks=(N+15)/16;
    if(j<chunks)sums[j]=subtree<16>(N,j*16,[&](int i){return ex[i];});
    it.barrier(sycl::access::fence_space::local_space);
    const float den=subtree<256>(chunks,0,[&](int i){return sums[i];});
    prob[j]=ex[j]/den;it.barrier(sycl::access::fence_space::local_space);
    auto put=[&](int rank,int index){selected[rank]=index;const float v=prob[index];rb.out(0).put(rank,index);rb.out(1).put(rank,v);
     if(rb.s.no>=4)for(int k=0;k<3;++k){rb.out(2).put(rank*3+k,k==0?index:k==1?0:rb.s.g.mid);rb.out(3).put(rank*3+k,k==0?index:k==1?0:rb.s.g.h);}};
    if constexpr(!MERGE){
     bool taken=false;
     for(int rank=0;rank<Top;++rank){
      const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);
      const uint32_t top=sycl::reduce_over_group(g,taken?0u:bits+1u,sycl::maximum<uint32_t>());
      const int index=sycl::reduce_over_group(g,(!taken&&bits+1u==top)?j:N,sycl::minimum<int>());
      if(j==index)taken=true;
      if(j==0)put(rank,index);
     }
    } else {
     uint32_t* cbits=bad+2;uint32_t* cidx=cbits+C;
     auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sgi=int(sg.get_group_linear_id());
     const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);bool taken=false;
     for(int k=0;k<Top;++k){
      const uint32_t top=sycl::reduce_over_group(sg,taken?0u:bits+1u,sycl::maximum<uint32_t>());
      const int index=sycl::reduce_over_group(sg,(!taken&&bits+1u==top)?j:N,sycl::minimum<int>());
      if(j==index){taken=true;cbits[sgi*Top+k]=bits;cidx[sgi*Top+k]=uint32_t(j);}
     }
     it.barrier(sycl::access::fence_space::local_space);
     if(sgi==0){
      constexpr int PER=C/32;uint32_t cb[PER],ci[PER];bool tk[PER];
      #pragma unroll
      for(int c=0;c<PER;++c){cb[c]=cbits[lane+32*c];ci[c]=cidx[lane+32*c];tk[c]=false;}
      for(int rank=0;rank<Top;++rank){
       uint32_t best=0;
       #pragma unroll
       for(int c=0;c<PER;++c)best=std::max(best,tk[c]?0u:cb[c]+1u);
       const uint32_t top=sycl::reduce_over_group(sg,best,sycl::maximum<uint32_t>());
       uint32_t mi=uint32_t(N);
       #pragma unroll
       for(int c=0;c<PER;++c)if(!tk[c]&&cb[c]+1u==top)mi=std::min(mi,ci[c]);
       const uint32_t index=sycl::reduce_over_group(sg,mi,sycl::minimum<uint32_t>());
       #pragma unroll
       for(int c=0;c<PER;++c)if(ci[c]==index)tk[c]=true;
       if(lane==0)put(rank,int(index));
      }
     }
    }

    // Only selected ties can affect the reference top-ten permutation.
    it.barrier(sycl::access::fence_space::local_space);
    bool internal=false;
    if(j==0)for(int k=1;k<Top;++k)internal|=prob[selected[k-1]]==prob[selected[k]];
    const int cutoff=selected[Top-1];
    const bool tied=sycl::any_of_group(g,internal||(j!=cutoff&&prob[j]==prob[cutoff]));
    if(tied){
     if(j==0){
      int* order=reference_indices.get_multi_ptr<sycl::access::decorated::no>().get();
      auto* stack=reference_frames.get_multi_ptr<sycl::access::decorated::no>().get();
      const float* probability=prob.get_multi_ptr<sycl::access::decorated::no>().get();
      bool valid=router_reference_sort::sort_indices_workspace(probability,order,N,stack);
      // Complete all checks before changing IDs or fused route descriptors.
      for(int rank=0;valid&&rank<Top;++rank){
       const int old=selected[rank],next=order[rank];
       valid=next>=0&&next<N&&prob[old]==prob[next];
       for(int previous=0;valid&&previous<rank;++previous)valid=order[previous]!=next;
       if(valid&&old!=next)valid=sycl::bit_cast<uint32_t>(rb.in(0).get(old))==sycl::bit_cast<uint32_t>(rb.in(0).get(next));
      }
      if(!valid){bad[0]=1;rb.fail();}
      else for(int rank=0;rank<Top;++rank){
       rb.out(0).put(rank,order[rank]);
       if(rb.s.no>=4){rb.out(2).put(rank*3,order[rank]);rb.out(3).put(rank*3,order[rank]);}
      }
     }
     it.barrier(sycl::access::fence_space::local_space);
     if(bad[0])return;
    }
    if(j==0){float sum=subtree<32>(Top,0,[&](int i){return rb.out(1).get(i);});for(int i=0;i<Top;++i)rb.out(1).put(i,rb.out(1).get(i)/sum);}
   }));});
 }
};
// HC combine and expert gather, F32 mode, without the generic accessor: each item handles four consecutive elements with
// the SimpleNew expression unchanged (stream + branch*(2*sigmoid(inject/4)); exact copies for the gather), and routes and
// validity exactly as before (an invalid id sets the sticky error, as the second gather phase did). Rows of a prefill
// chunk use the Spec row strides. OWNRT_SIMPLE_FAST=0 keeps the SimpleNew kernels.
struct CombineFast final:ownrt::SyclOperation {
 Spec spec;explicit CombineFast(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());const size_t n=spec.sizes[spec.ni],w=size_t(spec.site.shape[1]),quads=n/4;const int rows=spec.tokens;
  if(experts_v2::enabled("guard")){
   // Guard read once per 32-lane subgroup (broadcast) instead of by every item; same arithmetic per item.
   const size_t total=size_t(rows)*quads;
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((total+127)/128*128,128)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();
    if(sycl::group_broadcast(sg,sg.get_local_linear_id()==0?int(!*b.active()||b.failed()):0,0))return;
    const size_t i=it.get_global_linear_id();if(i>=total)return;
    const size_t r=i/quads,c=(i%quads)*4;const RowBound rb{b,int(r),b.s};
    const float* stream=static_cast<const float*>(rb.in(0).p);const float* branch=static_cast<const float*>(rb.in(1).p);const float* inject=static_cast<const float*>(rb.in(2).p);float* out=static_cast<float*>(rb.out(0).p);
    const float gate=2.f*ng::sigmoid(inject[c/w]/4.f);
    for(int j=0;j<4;++j)out[c+j]=stream[c+j]+branch[(c+j)%w]*gate;}));});
  }
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(size_t(rows)*quads)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> id){
   const size_t r=id[0]/quads,c=(id[0]%quads)*4;const RowBound rb{b,int(r),b.s};
   if(!*rb.active()||rb.failed())return;
   const float* stream=static_cast<const float*>(rb.in(0).p);const float* branch=static_cast<const float*>(rb.in(1).p);const float* inject=static_cast<const float*>(rb.in(2).p);float* out=static_cast<float*>(rb.out(0).p);
   const float gate=2.f*ng::sigmoid(inject[c/w]/4.f);
   for(int j=0;j<4;++j)out[c+j]=stream[c+j]+branch[(c+j)%w]*gate;}));});
 }
};
struct GatherFast final:ownrt::SyclOperation {
 Spec spec;explicit GatherFast(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());const int top=spec.g.top;const size_t n=spec.no_materialize_gather?0:spec.sizes[spec.ni+2],h=spec.sizes[1],per=size_t(top)+n/4;const int rows=spec.tokens;
  if(experts_v2::enabled("guard")){
   // Guard read once per 32-lane subgroup (broadcast) instead of by every item; same work per item.
   const size_t total=size_t(rows)*per;
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((total+127)/128*128,128)](sycl::handler& hd){hd.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();
    if(sycl::group_broadcast(sg,sg.get_local_linear_id()==0?int(!*b.active()||b.failed()):0,0))return;
    const size_t i=it.get_global_linear_id();if(i>=total)return;
    const size_t r=i/per,index=i%per;const RowBound rb{b,int(r),b.s};
    if(index<size_t(top)){const int j=int(index);float v=rb.in(0).get(j);bool valid=std::isfinite(v)&&v>=0&&v<float(rb.s.g.experts)&&std::floor(v)==v;int ex=valid?int(v):0;
     for(int k=0;k<3;++k){rb.out(0).put(j*3+k,k==0?ex:k==1?0:rb.s.g.mid);rb.out(1).put(j*3+k,k==0?ex:k==1?0:rb.s.g.h);}
     if(!valid)rb.fail();return;}
    const size_t c=(index-top)*4;const float* src=static_cast<const float*>(rb.in(1).p);float* dst=static_cast<float*>(rb.out(2).p);
    for(int j=0;j<4;++j)dst[c+j]=src[(c+j)%h];}));});
  }
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(size_t(rows)*per)](sycl::handler& hd){hd.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> id){
   const size_t r=id[0]/per,index=id[0]%per;const RowBound rb{b,int(r),b.s};
   if(!*rb.active()||rb.failed())return;
   if(index<size_t(top)){const int j=int(index);float v=rb.in(0).get(j);bool valid=std::isfinite(v)&&v>=0&&v<float(rb.s.g.experts)&&std::floor(v)==v;int ex=valid?int(v):0;
    for(int k=0;k<3;++k){rb.out(0).put(j*3+k,k==0?ex:k==1?0:rb.s.g.mid);rb.out(1).put(j*3+k,k==0?ex:k==1?0:rb.s.g.h);}
    if(!valid)rb.fail();return;}
   const size_t c=(index-top)*4;const float* src=static_cast<const float*>(rb.in(1).p);float* dst=static_cast<float*>(rb.out(2).p);
   for(int j=0;j<4;++j)dst[c+j]=src[(c+j)%h];}));});
 }
};
// OWNRT_EXPERTS_V2 "status" (lab 2026-10-26): the merged expert status check in one 32-lane subgroup. The generic
// form (simple(): 128 lanes, an active and a sticky-error read, then a float tree sum of (status!=0) per input and
// fail() when the total is nonzero) sets the error exactly when some status element is nonzero; here each lane ORs
// its strided elements and any_of_group decides. Same guards (inactive or already failed: nothing), same single store.
struct StatusFast final:ownrt::SyclOperation {
 Spec spec;explicit StatusFast(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(32,32)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id());
   if(sycl::group_broadcast(sg,lane==0?int(!*b.active()||b.failed()):0,0))return;
   bool any=false;
   for(int k=0;k+2<b.s.ni;++k){const View v=b.in(k);for(int j=lane;j<int(v.n);j+=32)any=any||v.get(j)!=0;}
   if(sycl::any_of_group(sg,any)&&lane==0)b.fail();
  }));});
 }
};
inline bool simple_fast(){static const bool on=[]{const char* e=std::getenv("OWNRT_SIMPLE_FAST");return !e||e[0]!='0';}();return on;}
// Argmax in one 1024-lane work-group per row: lane l scans indices l, l+1024, ... keeping its first maximum (strict >),
// then a work-group maximum of the values and a minimum of the indices that hold it. That is SimpleNew's result exactly
// (largest value, lowest index among equal values, +0 and -0 equal) for finite logits. Any non-finite logit runs
// SimpleNew's own fallback scan in one item and fails, as before. OWNRT_ARGMAX_FAST=0 keeps the two-phase kernel.
struct ArgmaxFast final:ownrt::SyclOperation {
 Spec spec;explicit ArgmaxFast(Spec s):spec(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());const int rows=spec.tokens;constexpr int W=1024;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(rows)*W,W)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it){
    const int r=int(it.get_group_linear_id()),lane=int(it.get_local_linear_id());const RowBound rb{b,r,b.s};auto g=it.get_group();
    if(!*rb.active()||rb.failed())return; // uniform across the work-group
    const int n=int(rb.in(0).n);int best=-1;float value=0.f;bool finite=true;
    for(int j=lane;j<n;j+=W){const float v=rb.in(0).get(j);finite=finite&&std::isfinite(v);if(best<0||v>value){best=j;value=v;}}
    const bool all_finite=sycl::all_of_group(g,finite);
    if(all_finite){
     const float top=sycl::reduce_over_group(g,best<0?-INFINITY:value,sycl::maximum<float>());
     const int index=sycl::reduce_over_group(g,(best>=0&&value==top)?best:INT_MAX,sycl::minimum<int>());
     if(lane==0)rb.out(0).put(0,index);
    }else if(lane==0){
     int fallback=0;for(int l=0;l<128;++l){int local=l;for(int j=l;j<n;j+=128)if(rb.in(0).get(j)>rb.in(0).get(local))local=j;if(l<n&&(rb.in(0).get(local)>rb.in(0).get(fallback)||(rb.in(0).get(local)==rb.in(0).get(fallback)&&local<fallback)))fallback=local;}
     rb.out(0).put(0,fallback);rb.fail();
    }
   }));});
 }
};
inline bool argmax_fast(){static const bool on=[]{const char* e=std::getenv("OWNRT_ARGMAX_FAST");return !e||e[0]!='0';}();return on;}
inline bool reference_route_tie_sort(){static const bool on=[]{
 const char* e=std::getenv("OWNRT_REFERENCE_ROUTE_TIE_SORT");if(!e||std::string(e)=="0")return false;
 if(std::string(e)=="1")return true;throw std::invalid_argument("OWNRT_REFERENCE_ROUTE_TIE_SORT must be 0 or 1");
 }();return on;}
inline bool route_fast(){static const bool on=[]{const char* e=std::getenv("OWNRT_ROUTE_FAST");return !e||e[0]!='0';}();return on;}
inline bool route_group(){static const bool on=[]{const char* e=std::getenv("OWNRT_ROUTE_GROUP");return e&&e[0]=='1';}();return on;}
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
  else if(mode==3){std::vector<float> scratch(tiny_local_floats(s));for(int g=0;g<tiny_groups(s);++g)tiny(b,g,ng::HostTeam{scratch.data()});}
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
  if(mode==1||mode==2)return ownrt::prepared_submit(q,[=](sycl::handler& h){h.single_task(packet26::checked([=]{if(mode_==1){ctrl[0]=*b.position();ctrl[1]=*b.active();ctrl[2]=b.failed();}else if(mode_==2){if(ctrl[2])b.fail();}}));});
  int groups=mode==3?tiny_groups(s):s.special==Special::normal&&s.op==Op::ple_gate?4:1,local=mode==3?tiny_local_floats(s):std::max(8192,s.g.h);
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(groups*128,128)](sycl::handler& h){sycl::local_accessor<float,1> scratch(local,h);h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto t=Team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()};if(mode_==3)tiny(b,it.get_group_linear_id(),t);else simple(b,it.get_group_linear_id(),t);}));});
 }
};
#endif
}
Launch submit_parallel(ownrt::Device& d,const Spec& s,std::span<const ownrt::Allocation> bindings,ownrt::Allocation control,ownrt::Allocation score,ownrt::Allocation probability,std::span<const ownrt::Event> deps){
 if(bindings.size()!=size_t(s.ni+s.no+s.nw+5)||bindings.size()>31)throw std::invalid_argument("adapter binding count");
#ifndef OWN_RT_HOST_ONLY
 if(s.op==Op::route&&reference_route_tie_sort()){
  if(s.special!=Special::normal||(s.implementation!=1&&s.implementation!=11)||s.sizes[0]!=512||s.site.shape[1]!=10||!s.f32_activations||(s.no!=2&&s.no!=4)||s.tokens<1||!route_fast()||(!experts_v2::enabled("route")&&!experts_v2::enabled("guard")))
   throw std::invalid_argument("reference tie sort unsupported route treatment");
 }
#endif

 if(s.f32_activations){
  // Exact mode: no BF16 activation buffer may reach a kernel, and only F32-capable implementations run.
  for(int j=0;j<s.ni+s.no;++j)if(s.types[j]==Scalar::bf16)throw std::invalid_argument("BF16 activation buffer in exact F32 mode");
  bool ported=s.special!=Special::normal||s.op==Op::norm||s.op==Op::silu_div4||s.op==Op::silu_product||s.op==Op::hc_mix||s.op==Op::conv||s.op==Op::gdn||s.op==Op::gdn_norm_gate||
   s.op==Op::moe_combine||s.op==Op::qsa_prepare||s.op==Op::qsa_append_pool||s.op==Op::qsa_select||s.op==Op::qsa_attention||s.op==Op::route||s.op==Op::expert_gather||s.op==Op::hc_combine||s.op==Op::argmax||s.op==Op::ple_add||s.op==Op::ple_gate;
  // round2's GDN (implementation 2) is the same arithmetic as the generic kernel with subgroup shuffles: F32-capable
  // (a.b/a.put follow the activation type, and F32 state equals the activation type here).
  bool generic_impl=s.implementation==0||s.implementation==1||s.implementation==11||s.implementation==12||(s.implementation==2&&s.op==Op::gdn);
  if(!ported||!generic_impl)throw std::invalid_argument("implementation "+std::to_string(s.implementation)+" has no exact F32 activation variant");
 }
 if(s.tokens!=1) {
  // Token rows run only on kernels that loop rows with single-row arithmetic: the generic/specialised kernels, and the
  // SimpleNew route/gather/combine kernels through their per-row binding offsets.
  const bool normal=s.special==Special::normal,simple=normal&&(s.implementation==1||s.implementation==11)&&(s.op==Op::route||s.op==Op::expert_gather||(s.op==Op::hc_combine&&!s.fused_combine_norm));
  const bool generic=normal&&(s.implementation<=1||s.implementation==11)&&!(s.op==Op::route||s.op==Op::expert_gather||(s.op==Op::hc_combine&&!s.fused_combine_norm)||s.op==Op::argmax||s.op==Op::ple_add||s.op==Op::ple_gate||s.op==Op::qsa_attention||s.op==Op::moe_combine);
  const bool round2_gdn=normal&&s.implementation==2&&s.op==Op::gdn; // loops token rows like the generic kernel
  // p49 split32 attention (implementation 12) indexes every binding by row r < tokens, with per-row counts and causal
  // bound; up to 4 rows (grouped prefill attention, OWNRT_PREFILL_ATTN_ROWS).
  const bool p49_rows=normal&&s.implementation==12&&s.op==Op::qsa_attention&&s.tokens<=4;
  if(!simple&&!generic&&!round2_gdn&&!p49_rows)throw std::invalid_argument("token rows: generic, specialised and SimpleNew route/gather/combine kernels only");
 }
 if(s.implementation==6&&s.special==Special::normal&&s.op==Op::route&&s.sizes[0]==512&&s.site.shape[1]==10)return route42::submit(d,s,bindings,deps);
 if(s.implementation==2&&s.special==Special::normal&&(s.op==Op::route||s.op==Op::argmax))return round2::submit_simple(d,s,bindings,deps);
 if(s.implementation&&s.special==Special::broadcast)return simple_new_submit<Op::hc_mix>(d,s,bindings,deps);
 if(s.implementation&&s.special==Special::normal){switch(s.op){
 case Op::route:if(s.sizes[0]==512&&s.site.shape[1]==10){
#ifndef OWN_RT_HOST_ONLY
  if(reference_route_tie_sort()){
   if(!route_fast())throw std::invalid_argument("reference tie sort requires RouteFast2");
   if(experts_v2::enabled("route")){RouteReferenceTie2<512,10,true> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
   if(experts_v2::enabled("guard")){RouteReferenceTie2<512,10,false> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
   throw std::invalid_argument("reference tie sort requires RouteFast2 treatment");
  }
  if(route_fast()&&experts_v2::enabled("route")){RouteFast2<512,10,true> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
  if(route_fast()&&experts_v2::enabled("guard")){RouteFast2<512,10,false> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
  if(route_fast()){RouteFast<512,10> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
  if(route_group()){RouteGroup<512,10> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
#endif
  return simple_new_submit<Op::route,512,10>(d,s,bindings,deps);}
  return simple_new_submit<Op::route>(d,s,bindings,deps);
 case Op::expert_gather:
#ifndef OWN_RT_HOST_ONLY
  if(s.f32_activations&&simple_fast()&&(s.no_materialize_gather||(s.types[1]==Scalar::f32&&s.types[s.ni+2]==Scalar::f32&&s.sizes[1]%4==0&&s.sizes[s.ni+2]%s.sizes[1]==0))){GatherFast op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
#endif
  return simple_new_submit<Op::expert_gather>(d,s,bindings,deps);
 case Op::hc_combine:if(!s.fused_combine_norm){
#ifndef OWN_RT_HOST_ONLY
  if(s.f32_activations&&simple_fast()&&s.types[0]==Scalar::f32&&s.types[1]==Scalar::f32&&s.types[2]==Scalar::f32&&s.types[s.ni]==Scalar::f32&&s.sizes[s.ni]%4==0&&s.site.shape[1]%4==0){CombineFast op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
#endif
  return simple_new_submit<Op::hc_combine>(d,s,bindings,deps);}break;
 case Op::argmax:
#ifndef OWN_RT_HOST_ONLY
  if(argmax_fast()){ArgmaxFast op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
#endif
  return simple_new_submit<Op::argmax>(d,s,bindings,deps);
 case Op::ple_add:return simple_new_submit<Op::ple_add>(d,s,bindings,deps);
 default:break;}}
 ng::Shape shape{};shape.capacity=s.g.context;shape.extent=s.extent;shape.budget=s.g.budget;shape.tokens=s.tokens;if(s.f32_activations)shape.flags|=ng::f32_activations_flag;
 if(s.special==Special::normal&&(s.op==Op::gdn||s.op==Op::conv)){
  const int input=s.op==Op::gdn?3:1;
  if(s.ni<=input||s.no!=2)throw std::invalid_argument("recurrent state binding shape");
  shape.flags|=recurrent_f32::admit(s.types[input],s.types[s.ni+1],Scalar::bf16,Scalar::f32,s.implementation,s.f32_activations);
 }
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
 // OWNRT_QSA_RAW_RING=1: a raw binding allocated as the 512-row ring (rank 1 plan, rank.hpp) selects ring indexing.
 if(use_ng&&shape.op==ng::pool&&qsaring::enabled()&&shape.capacity>qsaring::rows&&d.arena.row(a[6]).bytes==size_t(qsaring::rows)*128*(s.f32_activations?4:2))shape.flags|=qsaring::flag;
 // Packet15's GDN/QSA geometry is fixed to the real model. Mini's synthetic
 // geometry uses dimensioned parallel equations, never the interpreter control.
 bool tiny=s.g.h!=2560;
 bool tiny_core=tiny&&s.special==Special::normal&&(s.op==Op::gdn||s.op==Op::gdn_norm_gate||s.op==Op::qsa_prepare||s.op==Op::qsa_append_pool||s.op==Op::qsa_select||s.op==Op::qsa_attention);
 std::array<ownrt::Allocation,32> b{};std::copy(bindings.begin(),bindings.end(),b.begin());b[bindings.size()]=control;
 if(!use_ng&&!tiny_core&&s.special==Special::check_status&&s.tokens==1&&experts_v2::enabled("status")){StatusFast k(s);auto e=d.compute(k,bindings,deps);return {e,e,1};}
 if(!use_ng||tiny_core){Glue k(s,tiny_core?3:0);auto e=d.compute(k,std::span<const ownrt::Allocation>(b.data(),bindings.size()+1),deps);return {e,e,1};}
 // Validate before submitting anything, so a bad shape cannot strand a partial chain.
 ng::validate(shape);auto required=ng::required_bytes(shape);for(int j=0;j<19;++j)if(d.arena.row(a[j]).bytes<required[j])throw std::invalid_argument("adapter allocation too short at slot "+std::to_string(j));
 ownrt::Event first=0,last=0;uint32_t count=0;
 auto kernel=[&](ng::Shape sh){std::array<ownrt::Event,1> after{last};auto chain=last?std::span<const ownrt::Event>(after):deps;
  if(s.implementation>=7&&s.implementation<=10){auto e=p42::submit(d,sh,a,bindings[s.ni+s.no+s.nw],s.implementation,chain);last=e.last;if(!first)first=e.first;count+=e.passes;return;}
  if(s.implementation==3&&(sh.op==ng::attention_score||sh.op==ng::attention_softmax||sh.op==ng::attention_value)){auto e=p33r2::submit(d,sh,a,bindings[s.ni+s.no+s.nw],chain);last=e.last;if(!first)first=e.first;count+=e.passes;return;}
  if(s.implementation==2&&round2::supported(sh)){auto e=round2::submit(d,sh,a,bindings[s.ni+s.no+s.nw],chain);last=e.last;if(!first)first=e.first;count+=e.passes;return;}
  if(s.implementation&&specialised::supported(sh)){auto e=specialised::submit(d,sh,a,bindings[s.ni+s.no+s.nw],chain);last=e.last;if(!first)first=e.first;count+=e.passes;return;}
#ifdef OWN_RT_HOST_ONLY
  NgHost k(sh);last=d.compute(k,a,chain);
#else
  last=ng::submit(d,sh,a,chain);
#endif
  if(!first)first=last;++count;};
 if(s.implementation==12&&shape.op==ng::attention_score)return p49::attention(d,shape,a,bindings[s.ni+s.no+s.nw],deps);
 if((s.implementation==4||s.implementation==5)&&shape.op==ng::attention_score){auto e=p30integrated::attention(d,shape,a,unsigned(s.implementation-4),deps);return e;}
 kernel(shape);if(shape.op==ng::attention_score){shape.op=ng::attention_softmax;kernel(shape);shape.op=ng::attention_value;kernel(shape);}
 return {first,last,count};
}
}
