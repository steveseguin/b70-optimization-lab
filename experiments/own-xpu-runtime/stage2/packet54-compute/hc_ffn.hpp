#pragma once
#include "runtime_kernels.hpp"
#include "specialised.hpp"
#include "performance.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif

// Packet54: independent scheduling changes over packet49c's arithmetic.
// The ordinary layer is M=1. M=2 is two serial invocations using the same
// owner state, as in the production engine; it is not a changed batch tree.
namespace p54hc {
using integrated::Op;
struct Bound {
 integrated::Spec s;
 std::array<void*,32> p{};
 integrated::View in(unsigned j)const{return {p[j],s.sizes[j],s.types[j]};}
 integrated::View out(unsigned j)const{unsigned k=s.ni+j;return {p[k],s.sizes[k],s.types[k]};}
 unsigned tail()const{return s.ni+s.no+s.nw;}
 float* scratch()const{return static_cast<float*>(p[tail()]);}
 uint32_t* error()const{return static_cast<uint32_t*>(p[tail()+1]);}
 uint32_t* position()const{return static_cast<uint32_t*>(p[tail()+2]);}
 uint32_t* active()const{return static_cast<uint32_t*>(p[tail()+3]);}
 uint32_t failed()const{
#ifdef OWN_RT_HOST_ONLY
  return *error();
#else
  return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error()).load();
#endif
 }
 void fail()const{
#ifdef OWN_RT_HOST_ONLY
  *error()=1;
#else
  sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*error()).store(1);
#endif
 }
 float gain(unsigned i)const{return static_cast<const float*>(p[s.ni+s.no])[i];}
};
inline Bound bind(integrated::Spec s,std::span<void*const>p){Bound b{s,{}};std::copy(p.begin(),p.end(),b.p.begin());return b;}
inline bool admitted(Bound b,bool check_position,unsigned index){
 if(!*b.active()||b.failed())return false;
 if(check_position&&*b.position()>=unsigned(b.s.g.context)){if(!index)b.fail();return false;}
 return true;
}
// Stage0 is deliberately the production 32-leaf subtree, including its
// materialized FP32 partials. Only the second-stage ownership changes.
inline void norm_partial(Bound b,unsigned index){
 if(!admitted(b,true,index))return;
 unsigned row=index/80,chunk=index%80;
 b.scratch()[index]=specialised::subtree(2560,chunk,[&](int k){float v=b.in(0).get(row*2560+k);return v*v;});
}
inline void norm_output(Bound b,unsigned row,unsigned k,float inv){
 unsigned i=row*2560+k;
 float y=(b.in(0).get(i)*inv)*(b.gain(i)+float(bool(b.s.site.parameter)));
 b.out(0).put(i,y);
}
// The first two levels of the exact 80-leaf upper tree: consecutive groups
// of four. All 80 real leaves are retained. Later levels use the original
// conditional +0 right tails, not a reassociation or a hardware reduction.
inline float upper_leaf4(const float* p,unsigned lane){
 if(lane>=20)return 0.f;
 unsigned i=lane*4;return (p[i]+p[i+1])+(p[i+2]+p[i+3]);
}
inline bool upper80_finite(const float*p){for(unsigned i=0;i<80;++i)if(!std::isfinite(p[i]))return false;return true;}
inline float upper80_cpu(const float* p){
 // NaN operand selection can depend on scalar versus subgroup scheduling.
 // Retain the unchanged scalar upper tree on exceptional partials.
 if(!upper80_finite(p))return specialised::upper(p,80);
 float v[32]{};for(unsigned i=0;i<32;++i)v[i]=upper_leaf4(p,i);
 for(unsigned step=1;step<20;step*=2)for(unsigned i=0;i<20;i+=2*step)v[i]=v[i]+(i+step<20?v[i+step]:0.f);
 return v[0];
}
inline ng::Args norm_args(Bound b);
inline ng::Shape norm_shape(Bound b);
struct NormGuard {Bound b;int error(ng::Args)const{return int(b.failed());}void fail(ng::Args)const{b.fail();}};
inline void norm_exception(Bound b,unsigned index){
 specialised::body<ng::norm,1,2560,4>(norm_shape(b),norm_args(b),index,b.scratch(),NormGuard{b});
}
inline void norm_stage1_tile(Bound b,unsigned row,unsigned tile){
 if(!admitted(b,true,row*20+tile))return;
 if(!upper80_finite(b.scratch()+row*80)){for(unsigned lane=0;lane<32;++lane)norm_exception(b,row*640+tile*32+lane);return;}
 float inv=detmath::rsqrt(upper80_cpu(b.scratch()+row*80)/2560.f+1e-6f);
 for(unsigned lane=0;lane<32;++lane)for(unsigned j=0;j<4;++j)norm_output(b,row,tile*128+lane*4+j,inv);
}
inline void norm_cpu(Bound b){
 for(unsigned i=0;i<320;++i)norm_partial(b,i);
 for(unsigned row=0;row<4;++row)for(unsigned tile=0;tile<20;++tile)norm_stage1_tile(b,row,tile);
}
inline void mix4(Bound b,unsigned vector_index){
 if(!admitted(b,true,vector_index))return;
 unsigned first=vector_index*4;
 float sum[4]{};
 // Each dimension has the unchanged stream-0,1,2,3 left-associated sum.
 for(unsigned stream=0;stream<4;++stream)for(unsigned j=0;j<4;++j){
  unsigned i=stream*2560+first+j;
  sum[j]=sum[j]+ng::sigmoid(b.in(1).get(i))*b.in(0).get(i);
 }
 for(unsigned j=0;j<4;++j)b.out(0).put(first+j,sum[j]/4.f);
}
// Keeping a factor in a vector temporary can change the chosen NaN operand
// even without reassociating arithmetic. For exceptional inputs retain the
// production scalar expression, including recomputation of the sigmoid. A
// non-inlined leaf prevents the vector scheduler from hoisting its factor.
// The unchanged control below remains independent of this candidate helper.
__attribute__((noinline)) inline void combine_scalar_exception(Bound b,unsigned index){
 b.out(0).put(index,b.in(0).get(index)+b.in(1).get(index%b.s.site.shape[1])*(2.f*ng::sigmoid(b.in(2).get(index/b.s.site.shape[1])/4.f)));
}
inline void combine4(Bound b,unsigned vector_index){
 // Packet49c simple_body<hc_combine> has no position guard. Preserve it.
 if(!admitted(b,false,vector_index))return;
 unsigned first=vector_index*4,stream=first/2560;
 float inject=b.in(2).get(stream);
 float factor=2.f*ng::sigmoid(inject/4.f);
 for(unsigned j=0;j<4;++j){unsigned i=first+j;float residual=b.in(0).get(i),branch=b.in(1).get(i%2560);if(!std::isfinite(inject)||!std::isfinite(residual)||!std::isfinite(branch))combine_scalar_exception(b,i);else b.out(0).put(i,residual+branch*factor);}
}
inline ng::Args norm_args(Bound b){ng::Args a;a.p[0]=b.in(0).p;a.p[1]=b.p[b.s.ni+b.s.no];a.p[2]=b.out(0).p;a.p[15]=b.error();a.p[17]=b.position();a.p[18]=b.active();return a;}
inline ng::Shape norm_shape(Bound b){ng::Shape s;s.op=ng::norm;s.tokens=1;s.width=2560;s.heads=4;s.capacity=b.s.g.context;s.flags=8|unsigned(bool(b.s.site.parameter));return s;}
inline void control_norm(integrated::Spec spec,std::span<void*const>p){
 auto b=bind(spec,p);auto a=norm_args(b);auto s=norm_shape(b);
 for(size_t i=0;i<specialised::work_items(s,0);++i)specialised::body<ng::norm,0>(s,a,i,b.scratch(),specialised::HostGuard{});
 for(size_t i=0;i<specialised::work_items(s,1);++i)specialised::body<ng::norm,1>(s,a,i,b.scratch(),specialised::HostGuard{});
}
inline void control_mix(integrated::Spec spec,std::span<void*const>p){
 auto b=bind(spec,p);ng::Args a;a.p[0]=b.in(0).p;a.p[1]=b.in(1).p;a.p[2]=b.out(0).p;a.p[15]=b.error();a.p[17]=b.position();a.p[18]=b.active();
 ng::Shape s;s.op=ng::mix;s.tokens=1;s.width=2560;s.capacity=b.s.g.context;ng::cpu(s,a);
}
inline void control_combine(integrated::Spec spec,std::span<void*const>p){
 auto b=bind(spec,p);
 // Exact packet49c adapter.cpp simple_body<Op::hc_combine> leaf/guard.
 for(unsigned index=0;index<b.out(0).n;++index){if(!*b.active()||b.failed())continue;b.out(0).put(index,b.in(0).get(index)+b.in(1).get(index%b.s.site.shape[1])*(2.f*ng::sigmoid(b.in(2).get(index/b.s.site.shape[1])/4.f)));}
}
inline void candidate_norm(integrated::Spec spec,std::span<void*const>p){norm_cpu(bind(spec,p));}
inline void candidate_mix(integrated::Spec spec,std::span<void*const>p){auto b=bind(spec,p);for(unsigned i=0;i<640;++i)mix4(b,i);}
inline void candidate_combine(integrated::Spec spec,std::span<void*const>p){auto b=bind(spec,p);for(unsigned i=0;i<2560;++i)combine4(b,i);}
enum class Kind {norm,mix,combine};
template<Kind K,unsigned Stage=0>struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 integrated::Spec spec;
 explicit Kernel(integrated::Spec s):spec(s){}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(spec,p);
  if constexpr(K==Kind::norm){if constexpr(Stage==0)for(unsigned i=0;i<320;++i)norm_partial(b,i);else for(unsigned row=0;row<4;++row)for(unsigned tile=0;tile<20;++tile)norm_stage1_tile(b,row,tile);}
  else if constexpr(K==Kind::mix)for(unsigned i=0;i<640;++i)mix4(b,i);
  else for(unsigned i=0;i<2560;++i)combine4(b,i);
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(spec,p);
  if constexpr(K==Kind::norm&&Stage==1)return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(80*32,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),tile=it.get_global_linear_id()/32,row=tile/20;
   // One guard observation per subgroup keeps all shuffle lanes participating.
   unsigned ok=lane==0?unsigned(admitted(b,true,tile)):0;ok=sycl::group_broadcast(sg,ok,0);if(!ok)return;
   bool exceptional=false;if(lane<20)for(unsigned j=0;j<4;++j)exceptional=exceptional||!std::isfinite(b.scratch()[row*80+lane*4+j]);
   if(sycl::any_of_group(sg,exceptional)){norm_exception(b,row*640+(tile%20)*32+lane);return;}
   float v=upper_leaf4(b.scratch()+row*80,lane);
   for(unsigned step=1;step<20;step*=2){float rhs=sycl::select_from_group(sg,v,(lane+step)%32);if(lane<20&&lane%(2*step)==0)v=v+(lane+step<20?rhs:0.f);}
   float inv=lane==0?detmath::rsqrt(v/2560.f+1e-6f):0.f;inv=sycl::group_broadcast(sg,inv,0);
   for(unsigned j=0;j<4;++j)norm_output(b,row,(tile%20)*128+lane*4+j,inv);
  });});
  else return q.submit([&](sycl::handler&h){h.depends_on(deps);constexpr unsigned n=K==Kind::norm?320:K==Kind::mix?640:2560;h.parallel_for(sycl::range<1>(n),[=](sycl::id<1>i){if constexpr(K==Kind::norm)norm_partial(b,i[0]);else if constexpr(K==Kind::mix)mix4(b,i[0]);else combine4(b,i[0]);});});
 }
#endif
};
inline void validate(integrated::Spec s,std::span<const ownrt::Allocation>a,Kind k){
 if(s.special!=integrated::Special::normal||s.fused_combine_norm||s.site.shape[1]!=2560||s.no!=1||a.size()!=size_t(s.ni+s.no+s.nw+5))throw std::invalid_argument("packet54 HC production binding shape");
 unsigned data_inputs=k==Kind::norm?1:k==Kind::mix?2:3;
 if(s.ni!=int(data_inputs)&&s.ni!=int(data_inputs+2))throw std::invalid_argument("packet54 HC input binding count");
 if(k==Kind::norm&&(s.op!=Op::norm||s.nw!=1||s.sizes[0]!=10240||s.sizes[s.ni]!=10240||s.grids[0]!=iq3::Type::F32))throw std::invalid_argument("packet54 norm production shape");
 if(k==Kind::mix&&(s.op!=Op::hc_mix||s.nw!=0||s.sizes[0]!=10240||s.sizes[1]!=10240||s.sizes[s.ni]!=2560))throw std::invalid_argument("packet54 mix production shape");
 if(k==Kind::combine&&(s.op!=Op::hc_combine||s.nw!=0||s.sizes[0]!=10240||s.sizes[1]!=2560||s.sizes[2]!=4||s.sizes[s.ni]!=10240))throw std::invalid_argument("packet54 combine production shape");
 for(unsigned i=0;i<data_inputs;++i)if(s.types[i]!=flash::Scalar::bf16)throw std::invalid_argument("packet54 HC requires BF16 inputs");
 if(s.types[s.ni]!=flash::Scalar::bf16)throw std::invalid_argument("packet54 HC requires BF16 output");
 if(s.ni==int(data_inputs+2)){unsigned tail=s.ni+s.no+s.nw;for(unsigned i=data_inputs;i<data_inputs+2;++i)if(s.types[i]!=flash::Scalar::u32||s.sizes[i]!=1)throw std::invalid_argument("packet54 HC appended control type/extent");if(a[data_inputs]!=a[tail+3]||a[data_inputs+1]!=a[tail+1])throw std::invalid_argument("packet54 HC appended active/error identity");}
}
template<Kind K>inline integrated::Launch submit(ownrt::Device&d,integrated::Spec s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){
 validate(s,a,K);
 unsigned tail=s.ni+s.no+s.nw;
 for(unsigned i=0;i<a.size();++i){const auto&r=d.arena.row(a[i]);size_t need=i<unsigned(s.ni+s.no)?s.sizes[i]*flash::scalar_bytes(s.types[i]):i<tail?size_t(10240*4):i==tail?(K==Kind::norm?size_t(320*4):size_t(4)):i<tail+4?size_t(4):size_t(2);if(!r.live||r.bytes<need)throw std::invalid_argument("packet54 HC short/dead binding");}
 // Only the ordinary residual's read/write alias is admitted. No write may
 // overlap a gain, gate, scratch or control allocation.
 for(unsigned i=0;i<a.size();++i)if(i!=unsigned(s.ni)&&a[i]==a[s.ni]&&!(K==Kind::combine&&i==0))throw std::invalid_argument("packet54 HC output binding alias");
 if constexpr(K==Kind::norm)for(unsigned i=0;i<a.size();++i)if(i!=tail&&a[i]==a[tail])throw std::invalid_argument("packet54 norm scratch binding alias");
 Kernel<K,0>op(s);auto first=d.compute(op,a,deps);
 if constexpr(K==Kind::norm){Kernel<K,1>last(s);std::array after{first};auto end=d.compute(last,a,after);return {first,end,2};}
 return {first,first,1};
}
inline integrated::Launch submit_norm(ownrt::Device&d,integrated::Spec s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){return submit<Kind::norm>(d,s,a,deps);}
inline integrated::Launch submit_mix(ownrt::Device&d,integrated::Spec s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){return submit<Kind::mix>(d,s,a,deps);}
inline integrated::Launch submit_combine(ownrt::Device&d,integrated::Spec s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){return submit<Kind::combine>(d,s,a,deps);}
} // namespace p54hc
