#pragma once
// Raw-queue bindings of unchanged packet29 runtime kernel bodies.
#include "runtime_bodies.hpp"
namespace p39 {
class RuntimeStatus; class RuntimeCombine; class RuntimeNg;
inline sycl::event runtime_status(sycl::queue& q,Bound b,const uint32_t* status,std::vector<sycl::event> deps){
 p39_runtime::Bound d{};d.s.special=integrated::Special::check_status;d.s.ni=1;d.s.g.h=2560;d.s.sizes[0]=b.count;d.s.types[0]=flash::Scalar::u32;
 d.p[0]=const_cast<uint32_t*>(status);d.p[1]=b.scratch;d.p[2]=b.error;d.p[3]=const_cast<uint32_t*>(b.position);d.p[4]=const_cast<uint32_t*>(b.active);
 // The original Glue dispatch keeps its tiny/simple runtime mode in the capture.
 int mode=0;int groups=1,local=8192;
 return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> scratch(local,h);h.parallel_for<RuntimeStatus>(sycl::nd_range<1>(groups*128,128),guarded([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto t=p39_runtime::Team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()};if(mode==3)p39_runtime::tiny(d,int(it.get_group_linear_id()),t);else p39_runtime::simple(d,int(it.get_group_linear_id()),t);}));});
}
inline sycl::event runtime_combine(sycl::queue& q,Bound b,const uint16_t* branch,std::vector<sycl::event> deps){
 p39_runtime::Bound d{};d.s.op=integrated::Op::hc_combine;d.s.ni=3;d.s.no=1;d.s.site.shape[1]=int(b.rows);d.s.g.h=2560;
 for(unsigned j=0;j<4;++j)d.s.types[j]=flash::Scalar::bf16;
 d.s.sizes[0]=d.s.sizes[3]=4*b.rows;d.s.sizes[1]=b.rows;d.s.sizes[2]=4;
 d.p[0]=b.streams;d.p[1]=const_cast<uint16_t*>(branch);d.p[2]=const_cast<uint16_t*>(b.inject);d.p[3]=b.streams;d.p[4]=b.scratch;d.p[5]=b.error;d.p[6]=const_cast<uint32_t*>(b.position);d.p[7]=const_cast<uint32_t*>(b.active);
 int n=4*b.rows;
 return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for<RuntimeCombine>(sycl::range<1>(n),guarded([=](sycl::id<1> i){p39_runtime::simple_body<integrated::Op::hc_combine,0>(d,int(i[0]));}));});
}
inline sycl::event runtime_ng(sycl::queue& q,ng::Shape s,ng::Args a,std::vector<sycl::event> deps){
 int work=s.op==ng::gdn?32:128;
 return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> scratch(ng::local_floats(s),h);h.parallel_for<RuntimeNg>(sycl::nd_range<1>(size_t(ng::groups(s))*work,work),guarded([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{ng::group(s,a,int(it.get_group_linear_id()),p39_ng::DeviceTeam{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()});}));});
}
template<Kind E,unsigned Stage> sycl::event runtime_tail(sycl::queue& q,Bound b,std::vector<sycl::event> deps){
 if constexpr(E==Kind::down_status||E==Kind::expert_checks||(E==Kind::expert_act&&Stage<2))return runtime_status(q,b,(E==Kind::expert_act||E==Kind::expert_checks)&&Stage==1?b.peer_status:b.status,deps);
 else if constexpr(E==Kind::attention_combine||(E==Kind::shared_combine&&Stage==1))return runtime_combine(q,b,E==Kind::attention_combine?b.y:b.out,deps);
 else {
  ng::Shape s{};s.capacity=int(b.capacity);ng::Args a{};a.p.fill(b.error);a.p[15]=b.error;a.p[17]=const_cast<uint32_t*>(b.position);a.p[18]=const_cast<uint32_t*>(b.active);
  if constexpr(E==Kind::gdn_conv){s.op=ng::conv;s.width=b.rows;s.extra=1;s.flags=8;a.p[0]=b.y;a.p[1]=b.history;a.p[2]=const_cast<float*>(b.conv_weights);a.p[3]=b.out;a.p[4]=b.history;}
  else if constexpr(E==Kind::shared_combine){s.op=ng::moe_combine;s.width=b.rows;s.extra=1;a.p[0]=const_cast<uint16_t*>(b.mixture);a.p[1]=const_cast<float*>(b.one);a.p[2]=b.y;a.p[3]=const_cast<uint16_t*>(b.shared_gate);a.p[4]=b.out;}
  else {s.op=ng::activation;s.width=b.rows*b.count;s.extra=E!=Kind::silu_div4;a.p[0]=E==Kind::shared_act?const_cast<uint16_t*>(b.other):b.y;a.p[1]=E==Kind::shared_act?b.y:b.py;a.p[2]=b.out;}
  return runtime_ng(q,s,a,deps);
 }
}
} // namespace p39
