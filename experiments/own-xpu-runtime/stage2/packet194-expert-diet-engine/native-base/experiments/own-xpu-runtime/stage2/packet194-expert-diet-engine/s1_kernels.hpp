#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
// Packet183 S1 kernel structs (s1_submit.cpp issues them). Bodies are copies of p33::Kernel (Mode 0, Q6_K),
// p49c::DenseKernel (Q6_K K6144 attention_combine, stage 0) and
// p49dvirtual::SmallKernel with only the Q6_K lane call replaced by the
// metadata-scale lane of s1_lanes.hpp. Grids, bindings, validations, partial
// scratch layout, finishes and epilogues are the production ones.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/s1_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/s1_lanes.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/small_gemv.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p183 {
// ---- p33.dense.segment, Q6_K ------------------------------------------------
template<unsigned K,unsigned Split> struct SegKernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 p28::Bound b{};
 p28::Bound bind(std::span<void*const> p)const {auto d=b;d.w=static_cast<const uint8_t*>(p[0]);d.peer=static_cast<const uint8_t*>(p[1]);d.x=static_cast<const uint16_t*>(p[2]);d.y=static_cast<uint16_t*>(p[3]);d.py=static_cast<uint16_t*>(p[4]);d.routes=b.has_routes?static_cast<const iq3::Route*>(p[5]):nullptr;d.status=static_cast<uint32_t*>(p[6]);d.ps=static_cast<uint32_t*>(p[7]);d.scratch=static_cast<float*>(p[8]);return d;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto d=bind(p);
  for(unsigned slot=0;slot<d.count;++slot){
   auto r=d.routes?d.routes[slot]:iq3::Route{0,0,d.rows};
   bool ok=iq3::valid_route(r,d.experts,d.rows,d.rows);
   if(d.routes)d.status[slot]=!ok;
   #pragma omp parallel for num_threads(2) schedule(static) if(d.rows>=64)
   for(unsigned row=0;row<d.rows;++row){
    bool valid=ok&&row<r.row_count;float parts[4]{};
    for(unsigned part=0;part<Split;++part){
     float sums[32]{};auto range=iq3::kopt2::bounds(K,part,Split);
     if(valid)for(unsigned lane=0;lane<32;++lane){
      const unsigned source=(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb);
      sums[lane]=p33_lane<K>(d.w+source,d.x,unsigned(range.first),unsigned(range.second),lane);
     }
     parts[part]=iq3::tree32(sums);
    }
    float v=Split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);d.y[slot*d.rows+row]=iq3::bf16_bits(valid?v:iq3::bits_float(0x7fc00000));
   }
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto d=bind(p);
  const size_t groups=size_t(d.rows)*d.count*Split;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(groups*32,32)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),item=unsigned(it.get_group_linear_id()),logical=item/Split,part=item%Split;
   const unsigned row=logical%d.rows,slot=logical/d.rows;
   iq3::Route r{0,0,d.rows};if(d.routes)r=d.routes[slot];const bool ok=iq3::valid_route(r,d.experts,d.rows,d.rows),valid=ok&&row<r.row_count;
   float sum=0;
   if(valid){const unsigned source=(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb);auto range=iq3::kopt2::bounds(K,part,Split);
    sum=p33_lane<K>(d.w+source,d.x,unsigned(range.first),unsigned(range.second),lane);
   }
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0){float v=valid?sum:iq3::bits_float(0x7fc00000);if constexpr(Split==1)d.y[logical]=iq3::bf16_bits(v);else d.scratch[(logical*2)*4+part]=v;}
   if(lane==0&&row==0&&part==0&&d.routes)d.status[slot]=!ok;
  })));});
 }
#endif
};
#ifndef OWN_RT_HOST_ONLY
// p33 Finish, unchanged body: (v0+v1)+(v2+v3) of the split4 partials.
struct SegFinish final:ownrt::SyclOperation {unsigned n;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto s=static_cast<const float*>(p[0]);auto y=static_cast<uint16_t*>(p[1]);unsigned count=n;return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(count)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked([=](sycl::id<1> id){auto v=s+id[0]*8;y[id[0]]=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));})));});}
};
#endif
// ---- p49c attention_combine projection, Q6_K K6144 Split4, stage 0 ----------
struct AttnKernel final:p49c::Base {
 static constexpr unsigned K=6144,Split=4;static constexpr p39::Kind E=p39::Kind::attention_combine;
 p39::Bound shape;
 p39::Bound bind(std::span<void*const>p)const{return p49c::bind_dense(shape,p);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {
  auto b=bind(p);for(unsigned row=0;row<b.rows;++row){float partial[4]{};for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float lanes[32];for(unsigned lane=0;lane<32;++lane)lanes[lane]=p49c_lane<K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane);partial[part]=iq3::tree32(lanes);}auto y=iq3::bf16_bits((partial[0]+partial[1])+(partial[2]+partial[3]));b.y[row]=y;p49c::dense_tail_host<E>(b,row,y);}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=bind(p);
  return ownrt::prepared_submit(q,[=,p35_range2=sycl::nd_range<1>(((size_t(b.rows)*Split*32+256-1)/256)*256,256)](sycl::handler& h){
   h.parallel_for(p35_range2,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned logical=it.get_global_linear_id()/32,row=logical/Split,part=logical%Split;if(row>=b.rows)return;auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();auto bounds=iq3::kopt2::bounds(K,part,Split);float value=p49c_lane<K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane);
    for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
    if(!lane)b.scratch[row*8+part]=value;
   }));
  });
 }
#endif
};
// ---- p49d small.ffn.q6 tuple ------------------------------------------------
template<unsigned V>struct SmallKernel final:p49b::Base {
 std::array<p39::Bound,4> shapes;
 static constexpr unsigned groups(unsigned rows){return (rows+V-1)/V;}
 std::array<p39::Bound,4> bind(std::span<void*const>p)const{auto b=shapes;for(unsigned j=0;j<4;++j){b[j].w=static_cast<const uint8_t*>(p[j*3]);b[j].x=static_cast<const uint16_t*>(p[j*3+1]);b[j].y=static_cast<uint16_t*>(p[j*3+2]);}return b;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{auto bs=bind(p);for(unsigned j=0;j<4;++j){auto b=bs[j];for(unsigned row=0;row<b.rows;++row)b.y[row]=(j==0||j==3)?p49dvirtual::dense_host<Type::F32,2560,4,V>(b.w+size_t(row)*b.rb,b.x):small_host<2560,4,V>(b.w+size_t(row)*b.rb,b.x);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned g0=groups(b[0].rows),g1=groups(b[1].rows),g2=groups(b[2].rows),total=g0+g1+g2+groups(b[3].rows);
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(total)*128,128)](sycl::handler& h){sycl::local_accessor<float,1>scratch(4*V,h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned group=it.get_group_linear_id();auto s=scratch.template get_multi_ptr<sycl::access::decorated::no>().get();
    if(group<g0)p49dvirtual::dense_device<Type::F32,2560,4,V,p39::Kind::expert_checks>(b[0],group,it,s);
    else if(group<g0+g1)small_device<2560,4,V,p39::Kind::expert_checks>(b[1],group-g0,it,s);
    else if(group<g0+g1+g2)small_device<2560,4,V,p39::Kind::expert_checks>(b[2],group-g0-g1,it,s);
    else p49dvirtual::dense_device<Type::F32,2560,4,V,p39::Kind::expert_checks>(b[3],group-g0-g1-g2,it,s);
   }));});
 }
#endif
};
} // namespace p183
