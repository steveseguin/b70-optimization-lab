#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/prepared_submission.hpp"
#endif
#line 1
#pragma once
// Selected packet51 winners, preserving their arithmetic bodies. See INTEGRATION.md.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p39_fused.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/route42.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p49c {
using iq3::Type;
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
inline uint32_t load32(const uint8_t* p){
#if defined(__SYCL_DEVICE_ONLY__)
 return *reinterpret_cast<const uint32_t*>(p);
#else
 uint32_t value;std::memcpy(&value,p,4);return value;
#endif
}
// Keep the four production passes and all global scratch bytes. Stage2 caches
// normalized values in workgroup-local memory, including the rounded division
// before ranking: ranking raw logits/exponentials would change ties.
inline void route_exp_host(route42::Args a){
 if(!*a.active||a.failed())return;
 float maximum=-INFINITY;for(unsigned j=0;j<32;++j)maximum=std::max(maximum,a.scratch[j]);
 for(unsigned j=0;j<512;++j)a.scratch[64+j]=detmath::exp(a.in().get(j)-maximum);
 for(unsigned chunk=0;chunk<32;++chunk){float values[16];for(unsigned lane=0;lane<16;++lane)values[lane]=a.scratch[64+chunk*16+lane];for(unsigned width=1;width<16;width*=2)for(unsigned lane=0;lane<16;lane+=2*width)values[lane]=values[lane]+values[lane+width];a.scratch[32+chunk]=values[0];}
}
inline void route_rank_host(route42::Args a){
 if(!*a.active||a.failed())return;
 float values[512];float den=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
 for(unsigned j=0;j<512;++j)values[j]=a.scratch[64+j]/den;
 for(unsigned j=0;j<512;++j){unsigned rank=0;for(unsigned k=0;k<512;++k)rank+=values[k]>values[j]||(values[k]==values[j]&&k<j);route42::output<512,10>(a,j,rank);}
}
template<unsigned Stage>struct RouteKernel final:Base {
 integrated::Spec spec;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto a=route42::bind(spec,p);if constexpr(Stage==2)route_rank_host(a);else if constexpr(Stage==1)route_exp_host(a);else for(unsigned i=0;i<(Stage==4?1:32);++i)route42::phase<Stage,512,10>(a,i);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {auto a=route42::bind(spec,p);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(512,256),p35_range1=sycl::range<1>(Stage==4?1:32),p35_range2=sycl::nd_range<1>(64*256,256)](sycl::handler& h){
  if constexpr(Stage==1){sycl::local_accessor<float,1> maximum(1,h);
   h.parallel_for(p35_range0,[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    if(!*a.active||a.failed())return;
    unsigned j=it.get_global_linear_id();if(it.get_local_linear_id()==0){float value=-INFINITY;for(unsigned chunk=0;chunk<32;++chunk)value=std::max(value,a.scratch[chunk]);maximum[0]=value;}
    it.barrier(sycl::access::fence_space::local_space);
    float value=detmath::exp(a.in().get(j)-maximum[0]);a.scratch[64+j]=value;
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
    // Each half subgroup is exactly one original adjacent subtree<16>.
    for(unsigned width=1;width<16;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
    if(lane%16==0)a.scratch[32+j/16]=value;
   });
  }else if constexpr(Stage!=2)h.parallel_for(p35_range1,[=](sycl::id<1>id){route42::phase<Stage,512,10>(a,id[0]);});
  else {sycl::local_accessor<float,1> cached(513,h);h.parallel_for(p35_range2,[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   if(!*a.active||a.failed())return;
   unsigned local=it.get_local_linear_id(),lane=local%32,index=it.get_group_linear_id()*8+local/32;
   if(local==0)cached[512]=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
   it.barrier(sycl::access::fence_space::local_space);
   for(unsigned j=local;j<512;j+=256)cached[j]=a.scratch[64+j]/cached[512];
   it.barrier(sycl::access::fence_space::local_space);
   float value=cached[index];unsigned rank=0;for(unsigned k=lane;k<512;k+=32)rank+=cached[k]>value||(cached[k]==value&&k<index);
   auto sg=it.get_sub_group();for(unsigned width=1;width<32;width*=2){unsigned rhs=sycl::select_from_group(sg,rank,(lane+width)%32);if(lane%(2*width)==0)rank+=rhs;}
   if(!lane)route42::output<512,10>(a,index,rank);
  });}
 });}
#endif
};
inline integrated::Launch route_submit(ownrt::Device&d,const integrated::Spec&s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){
 unsigned tail=s.ni+s.no+s.nw;
 if(s.op!=integrated::Op::route||s.special!=integrated::Special::normal||s.sizes[0]!=512||s.site.shape[1]!=10||s.nw||!(s.ni==1||s.ni==3)||!(s.no==2||s.no==4)||a.size()!=tail+5)throw std::invalid_argument("p49c route ABI");
 for(unsigned j=0;j<a.size();++j){const auto&r=d.arena.row(a[j]);size_t n=j<tail?s.sizes[j]*flash::scalar_bytes(s.types[j]):j==tail?(64+1024)*4:j==tail+4?1:4;if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<n||uintptr_t(r.pointer)%4)throw std::invalid_argument("p49c route extent/alignment");}
 for(unsigned j=0;j<s.no;++j){if(s.sizes[s.ni+j]<(j<2?10u:30u))throw std::invalid_argument("p49c route output extent");for(unsigned k=0;k<a.size();++k)if(k!=s.ni+j&&a[s.ni+j]==a[k])throw std::invalid_argument("p49c route output alias");}
 // Production ni=3 carries explicit error/active inputs that intentionally
 // repeat the tail controls. Preserve route42's admission: tail controls are
 // mutually distinct, and scratch never aliases an input or output.
 for(unsigned j=tail;j<tail+4;++j)for(unsigned k=tail;k<j;++k)if(a[j]==a[k])throw std::invalid_argument("p49c route scratch/control alias");
 for(unsigned j=0;j<tail;++j)if(a[j]==a[tail])throw std::invalid_argument("p49c route scratch alias");
 integrated::Launch result{};
 auto issue=[&]<unsigned Stage>(){RouteKernel<Stage> op;op.spec=s;std::array after{result.last};auto event=d.compute(op,a,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=event;result.last=event;++result.passes;};
 issue.template operator()<0>();issue.template operator()<1>();issue.template operator()<2>();issue.template operator()<4>();return result;
}

template<Type T,unsigned K>inline float dense_lane(const uint8_t* w,const uint16_t* x,unsigned begin,unsigned end,unsigned lane){
 static_assert(T==Type::Q6_K||T==Type::Q8_0||T==Type::F32);
 float sum=0;
 for(unsigned k=begin+lane*8;k<end;k+=256){
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
  float scale=0;uint32_t lo=0,hi=0;
  if constexpr(T!=Type::F32){constexpr unsigned group=T==Type::Q6_K?16:32;scale=iq3::bits_float(load32(w+K+4*(k/group)));lo=load32(w+k);hi=load32(w+k+4);}
  #pragma unroll
  for(unsigned j=0;j<8;++j){float value;
   if constexpr(T==Type::F32)value=iq3::bits_float(load32(w+4*(k+j)));
   else value=scale*float(iq3::signed8(uint8_t(((j<4?lo:hi)>>(8*(j%4)))&255)));
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits=inputs[j];
#else
   uint16_t bits=x[k+j];
#endif
   float product=value*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
  }
 }
 return sum;
}
inline p39::Bound bind_dense(p39::Bound b,std::span<void*const>p){
 b.w=static_cast<const uint8_t*>(p[0]);b.peer=static_cast<const uint8_t*>(p[1]);b.x=static_cast<const uint16_t*>(p[2]);b.y=static_cast<uint16_t*>(p[3]);b.py=static_cast<uint16_t*>(p[4]);b.routes=static_cast<const iq3::Route*>(p[5]);b.status=static_cast<uint32_t*>(p[6]);b.peer_status=static_cast<uint32_t*>(p[7]);b.scratch=static_cast<float*>(p[8]);b.other=static_cast<const uint16_t*>(p[9]);b.out=static_cast<uint16_t*>(p[10]);b.streams=static_cast<uint16_t*>(p[11]);b.inject=static_cast<const uint16_t*>(p[12]);b.mixture=static_cast<const uint16_t*>(p[13]);b.shared_gate=static_cast<const uint16_t*>(p[14]);b.one=static_cast<const float*>(p[15]);b.error=static_cast<uint32_t*>(p[16]);b.active=static_cast<const uint32_t*>(p[17]);b.position=static_cast<const uint32_t*>(p[18]);return b;
}
template<p39::Kind E>inline void dense_tail_host(p39::Bound b,unsigned row,uint16_t value){
 if constexpr(E==p39::Kind::silu_div4||E==p39::Kind::attention_combine){if(!*b.active||*b.error)return;if(!p39::position_valid<E>(b)){*b.error=1;return;}p39::row_tail<E>(b,row,value,0);}
}
#ifndef OWN_RT_HOST_ONLY
template<p39::Kind E>inline void dense_tail_device(p39::Bound b,unsigned row,uint16_t value){
 if constexpr(E==p39::Kind::silu_div4){auto error=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);if(!*b.active||error.load())return;if(!p39::position_valid<E>(b)){uint32_t expected=0;error.compare_exchange_strong(expected,1);return;}p39::row_tail<E>(b,row,value,0);}
}
#endif
// Kind::expert_checks is the no-epilogue sentinel for non-routed dense calls.
// Split4 HC work stays within one row/workgroup, keeping its four partials and
// the BF16 activation boundary. Attention keeps its original global partials.
template<Type T,unsigned K,unsigned Split,p39::Kind E,unsigned Stage=0>struct DenseKernel final:Base {
 static_assert(Split==1||Split==4);static_assert(K%256==0||K==320);
 static constexpr bool attention=E==p39::Kind::attention_combine;
 p39::Bound shape;
 p39::Bound bind(std::span<void*const>p)const{return bind_dense(shape,p);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {
  if constexpr(Stage==0){auto b=bind(p);for(unsigned row=0;row<b.rows;++row){float partial[4]{};for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float lanes[32];for(unsigned lane=0;lane<32;++lane)lanes[lane]=dense_lane<T,K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane);partial[part]=iq3::tree32(lanes);}auto y=iq3::bf16_bits(Split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]));b.y[row]=y;dense_tail_host<E>(b,row,y);}}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=bind(p);
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(((size_t(b.rows)+255)/256)*256,256),p35_range1=sycl::nd_range<1>(size_t(b.rows)*128,128),p35_range2=sycl::nd_range<1>(((size_t(b.rows)*Split*32+256-1)/256)*256,256)](sycl::handler& h){
   if constexpr(Stage==1){static_assert(attention&&Split==4);sycl::local_accessor<float,1> factor(4,h);
    h.parallel_for(p35_range0,[=](sycl::nd_item<1>it){
     unsigned row=it.get_global_linear_id(),local=it.get_local_linear_id();bool enabled=*b.active&&!sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).load();
     if(local<4&&enabled)factor[local]=2.f*ng::sigmoid(p39::widen(b.inject[local])/4.f);
     it.barrier(sycl::access::fence_space::local_space);
     if(row>=b.rows)return;auto v=b.scratch+row*8;uint16_t y=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));b.y[row]=y;
     if(enabled)for(unsigned stream=0;stream<4;++stream){unsigned j=stream*b.rows+row;b.streams[j]=iq3::bf16_bits(p39::widen(b.streams[j])+p39::widen(y)*factor[stream]);}
    });
   }else if constexpr(Split==4&&!attention){sycl::local_accessor<float,1> partial(4,h);
    h.parallel_for(p35_range1,[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
     unsigned row=it.get_group_linear_id(),part=it.get_local_linear_id()/32;auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();auto bounds=iq3::kopt2::bounds(K,part,4);float value=dense_lane<T,K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane);
     for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
     if(!lane)partial[part]=value;it.barrier(sycl::access::fence_space::local_space);
     if(it.get_local_linear_id()==0){uint16_t y=iq3::bf16_bits((partial[0]+partial[1])+(partial[2]+partial[3]));b.y[row]=y;dense_tail_device<E>(b,row,y);}
    });
   }else {
    h.parallel_for(p35_range2,[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
     unsigned logical=it.get_global_linear_id()/32,row=logical/Split,part=logical%Split;if(row>=b.rows)return;auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();auto bounds=iq3::kopt2::bounds(K,part,Split);float value=dense_lane<T,K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane);
     for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
     if(!lane){if constexpr(attention)b.scratch[row*8+part]=value;else b.y[row]=iq3::bf16_bits(value);}
    });
   }
  });
 }
#endif
};
} // namespace p49c
