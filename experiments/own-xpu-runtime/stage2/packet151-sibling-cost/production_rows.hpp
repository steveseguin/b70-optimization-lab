#pragma once
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/native-base/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/prepared_submission.hpp"
#endif
// Packet68c: packet33 segment and packet49c vector kernels with two independent
// accumulators. K, split, workgroup and subgroup geometry remain compile-time.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/batched_rows.hpp"
namespace p68c {
template<Type T,unsigned K,bool Vector=false>
inline std::array<float,2> production_lane(const uint8_t* w,const uint16_t* x0,
 const uint16_t* x1,unsigned begin,unsigned end,unsigned lane){
 std::array<float,2> sum{};
 for(unsigned tile=begin+lane*8;tile<end;tile+=256){
  float scale=0;uint32_t lo=0,hi=0;
  if constexpr(T==Type::Q6_K||T==Type::Q8_0){
   constexpr unsigned group=T==Type::Q6_K?16:32;
   if constexpr(Vector){scale=iq3::bits_float(p49c::load32(w+K+4*(tile/group)));lo=p49c::load32(w+tile);hi=p49c::load32(w+tile+4);}
   else scale=iq3::bits_float(iq3::u32(w+K+4*(tile/group)));
  }
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> a,b;
  if constexpr(Vector){a.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x0+tile));b.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x1+tile));}
#endif
  #pragma unroll
  for(unsigned j=0;j<8;++j)if(tile+j<end){
   float weight;
   if constexpr(T==Type::Q6_K||T==Type::Q8_0){
    if constexpr(Vector)weight=scale*float(iq3::signed8(uint8_t(((j<4?lo:hi)>>(8*(j%4)))&255)));
    else weight=scale*float(iq3::signed8(w[tile+j]));
   }else weight=iq3::decode(T,w+(tile+j)*iq3::layout(T).bytes,0);
   uint16_t bits0,bits1;
#if defined(__SYCL_DEVICE_ONLY__)
   if constexpr(Vector){bits0=a[j];bits1=b[j];}else
#endif
   {bits0=x0[tile+j];bits1=x1[tile+j];}
   float product0=weight*iq3::bits_float(uint32_t(bits0)<<16);sum[0]=sum[0]+product0;
   float product1=weight*iq3::bits_float(uint32_t(bits1)<<16);sum[1]=sum[1]+product1;
  }
 }
 return sum;
}
struct ProductionBound {
 const uint8_t*w;const uint16_t*x[2];uint16_t*y[2];float*scratch[2];
 uint16_t*streams[2];const uint16_t*inject[2];uint32_t*error[2];const uint32_t*active[2];
};
inline ProductionBound production_bind(std::span<void*const>p){
 return {(const uint8_t*)p[0],{(const uint16_t*)p[1],(const uint16_t*)p[2]},
 {(uint16_t*)p[3],(uint16_t*)p[4]},{(float*)p[5],(float*)p[6]},
 {(uint16_t*)p[7],(uint16_t*)p[8]},{(const uint16_t*)p[9],(const uint16_t*)p[10]},
 {(uint32_t*)p[11],(uint32_t*)p[12]},{(const uint32_t*)p[13],(const uint32_t*)p[14]}};
}
template<Type T,unsigned K,unsigned Split,bool Attention=false>struct ProductionDense final:Base {
 unsigned rows=0,rb=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=production_bind(p);
  for(unsigned row=0;row<rows;++row){float parts[2][4]{};
   for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float lanes[2][32];
    for(unsigned lane=0;lane<32;++lane){auto v=production_lane<T,K,Attention>(b.w+size_t(row)*rb,b.x[0],b.x[1],bounds.first,bounds.second,lane);for(unsigned r=0;r<2;++r)lanes[r][lane]=v[r];}
    for(unsigned r=0;r<2;++r)parts[r][part]=iq3::tree32(lanes[r]);
   }
   for(unsigned r=0;r<2;++r){auto v=parts[r];auto y=iq3::bf16_bits(Split==1?v[0]:(v[0]+v[1])+(v[2]+v[3]));b.y[r][row]=y;
    if constexpr(Attention)if(*b.active[r]&&!*b.error[r])for(unsigned s=0;s<4;++s){unsigned j=s*rows+row;b.streams[r][j]=iq3::bf16_bits(p39::widen(b.streams[r][j])+p39::widen(y)*(2.f*ng::sigmoid(p39::widen(b.inject[r][s])/4.f)));}
   }
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=production_bind(p);auto n=rows,stride=rb;
  // packet33: one SG/workgroup. packet49c attention: eight SG/workgroup,
  // each retaining one original split and the original global partial layout.
  constexpr unsigned WG=Attention?256:32;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(((size_t(n)*Split*32+WG-1)/WG)*WG,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned logical=it.get_global_linear_id()/32,row=logical/Split,part=logical%Split;if(row>=n)return;
    unsigned lane=it.get_sub_group().get_local_linear_id();auto bounds=iq3::kopt2::bounds(K,part,Split);
    auto v=production_lane<T,K,Attention>(b.w+size_t(row)*stride,b.x[0],b.x[1],bounds.first,bounds.second,lane);
    #pragma unroll
    for(unsigned r=0;r<2;++r){v[r]=tree(it.get_sub_group(),v[r]);if(!lane){if constexpr(Split==1)b.y[r][row]=iq3::bf16_bits(v[r]);else b.scratch[r][row*8+part]=v[r];}}
   });});
 }
#endif
};
template<bool Attention>struct ProductionFinish final:Base {
 unsigned rows=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>)const override{} // host primary already finishes
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=production_bind(p);unsigned n=rows;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);
   if constexpr(Attention){sycl::local_accessor<float,1>factor(8,h);
    h.parallel_for(sycl::nd_range<1>(((size_t(n)+255)/256)*256,256),[=](sycl::nd_item<1>it){
     unsigned row=it.get_global_linear_id(),local=it.get_local_linear_id();bool enabled[2];
     #pragma unroll
     for(unsigned r=0;r<2;++r){enabled[r]=*b.active[r]&&!sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error[r]).load();if(local<4&&enabled[r])factor[r*4+local]=2.f*ng::sigmoid(p39::widen(b.inject[r][local])/4.f);}
     it.barrier(sycl::access::fence_space::local_space);if(row>=n)return;
     #pragma unroll
     for(unsigned r=0;r<2;++r){auto v=b.scratch[r]+row*8;auto y=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));b.y[r][row]=y;
      if(enabled[r])for(unsigned s=0;s<4;++s){unsigned j=s*n+row;b.streams[r][j]=iq3::bf16_bits(p39::widen(b.streams[r][j])+p39::widen(y)*factor[r*4+s]);}
     }
    });
   }else h.parallel_for(sycl::range<1>(n),[=](sycl::id<1>id){
    #pragma unroll
    for(unsigned r=0;r<2;++r){auto v=b.scratch[r]+id[0]*8;b.y[r][id[0]]=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));}
   });
  });
 }
#endif
};
template<Type T,unsigned K,unsigned Split,bool Attention=false>
inline integrated::Launch production_issue(ownrt::Device&d,const integrated::Matrix&a,const integrated::Matrix&b,std::span<const ownrt::Allocation>ids){
 ProductionDense<T,K,Split,Attention>op;op.rows=a.rows;op.rb=integrated::arithmetic::row_bytes(T,K,Split==4?7:6);
 auto e=d.compute(op,ids,{});integrated::Launch out{e,e,1};
#ifndef OWN_RT_HOST_ONLY
 if constexpr(Split==4){ProductionFinish<Attention>finish;finish.rows=a.rows;std::array after{e};out.last=d.compute(finish,ids,after);out.passes=2;}
#endif
 return out;
}
template<Type T,unsigned K>inline integrated::Launch production_split(ownrt::Device&d,const integrated::Matrix&a,const integrated::Matrix&b,unsigned split,std::span<const ownrt::Allocation>ids){
 if(split==1)return production_issue<T,K,1>(d,a,b,ids);
 return production_issue<T,K,4>(d,a,b,ids);
}
inline integrated::Launch production_dense(ownrt::Device&d,const integrated::Matrix&a,const integrated::Matrix&b,unsigned variant,bool attention,std::span<const ownrt::Allocation>tail){
 unsigned split=(variant==1||variant==4||variant==7)?4:1;
 if(a.w!=b.w||a.type!=b.type||a.rows!=b.rows||a.columns!=b.columns||a.count!=1||b.count!=1||a.experts!=1||b.experts!=1||a.routes||b.routes||a.activation!=Type::BF16||b.activation!=Type::BF16||a.output_type!=Type::BF16||b.output_type!=Type::BF16||a.fp32||b.fp32)throw std::invalid_argument("68c dense pair identity");
 if(tail.size()!=8)throw std::invalid_argument("68c dense tail binding");
 std::array<ownrt::Allocation,15>ids{a.w,a.x,b.x,a.y,b.y,a.workspace,b.workspace};std::copy(tail.begin(),tail.end(),ids.begin()+7);
 size_t rb=integrated::arithmetic::row_bytes(a.type,a.columns,variant);
 size_t bytes[]={a.rows*rb,a.columns*2,b.columns*2,a.rows*2,b.rows*2,split==4?a.rows*32:4,split==4?b.rows*32:4,attention?a.rows*8:2,attention?b.rows*8:2,attention?8u:2u,attention?8u:2u,4,4,4,4};
 for(unsigned i=0;i<ids.size();++i){auto&r=d.arena.row(ids[i]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes[i]||uintptr_t(r.pointer)%(i==1||i==2||i==3||i==4||i==7||i==8||i==9||i==10?2:4))throw std::invalid_argument("68c production dense extent/alignment");}
 for(unsigned i:{3u,4u,5u,6u})for(unsigned j=0;j<7;++j)if(i!=j&&ids[i]==ids[j])throw std::invalid_argument("68c dense write alias");
 if(attention){if(a.type!=Type::Q6_K||a.columns!=6144||split!=4)throw std::invalid_argument("68c attention shape");return production_issue<Type::Q6_K,6144,4,true>(d,a,b,ids);}
 // Only the production segment shapes are admitted here. Other classes stay
 // explicit serial M=1 until their own production-derived kernel is selected.
#define SHAPE(T,K) if(a.type==Type::T&&a.columns==K)return production_split<Type::T,K>(d,a,b,split,ids)
 SHAPE(Q6_K,2560);SHAPE(Q8_0,2560);SHAPE(Q8_0,640);SHAPE(Q8_0,320);SHAPE(F32,10240);
#undef SHAPE
 throw std::invalid_argument("68c unsupported production segment shape");
}
}
