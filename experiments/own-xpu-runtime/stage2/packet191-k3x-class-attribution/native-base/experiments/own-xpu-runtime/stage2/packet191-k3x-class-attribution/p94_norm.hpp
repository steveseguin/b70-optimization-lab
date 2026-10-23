#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p94_norm.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/build/checked/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/build/checked/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/p60_kernels.hpp"
namespace p94norm {
// Exactly p60 norm_output, including gain+positive-zero and the BF16 boundary.
inline uint16_t input(p60::Bound b,unsigned k,float inv,bool regenerate){
 return regenerate?iq3::bf16_bits((p60::get(b.x,k)*inv)*(b.gain[k]+0.f)):b.norm[k];
}
// Dedicated Q8/F32 low/injection chains. The only delta from p49c::dense_lane
// is the BF16 input producer. Product/add order, scale loads and split stay put.
template<iq3::Type T>inline float lane(const uint8_t*w,p60::Bound b,float inv,bool regenerate,unsigned begin,unsigned end,unsigned lane){
 static_assert(T==iq3::Type::Q8_0||T==iq3::Type::F32);
 float sum=0.f;
 for(unsigned k=begin+lane*8;k<end;k+=256){
  float scale=0.f;uint32_t lo=0,hi=0;
  if constexpr(T!=iq3::Type::F32){scale=iq3::bits_float(p49c::load32(w+p60::K+4*(k/32)));lo=p49c::load32(w+k);hi=p49c::load32(w+k+4);}
  #pragma unroll
  for(unsigned j=0;j<8;++j){float value;
   if constexpr(T==iq3::Type::F32)value=iq3::bits_float(p49c::load32(w+4*(k+j)));
   else value=scale*float(iq3::signed8(uint8_t(((j<4?lo:hi)>>(8*(j%4)))&255)));
   uint16_t bits=input(b,k+j,inv,regenerate);
   float product=value*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
  }
 }
 return sum;
}
inline void host(p60::Bound b){
 bool regenerate=p60::enabled(b);
 if(*b.active&&!*b.error&&*b.position>=b.capacity)*b.error=1;
 float inv[4]{};
 if(regenerate)for(unsigned stream=0;stream<4;++stream){
  float partial[128]{};
  for(unsigned c=0;c<80;++c){partial[c]=specialised::subtree(p60::H,c,[&](int k){float x=p60::get(b.x,stream*p60::H+k);return x*x;});b.scratch[stream*80+c]=partial[c];}
  float roots[4];for(unsigned g=0;g<4;++g)roots[g]=iq3::tree32(partial+g*32);
  float total=(roots[0]+roots[1])+(roots[2]+roots[3]);inv[stream]=detmath::rsqrt(total/float(p60::H)+1e-6f);
  for(unsigned k=0;k<p60::H;++k)p60::norm_output(b,stream,k,inv[stream]);
 }
 for(unsigned row=0;row<p60::L+p60::S;++row){
  float partial[4];for(unsigned part=0;part<4;++part){
   auto bounds=iq3::kopt2::bounds(p60::K,part,4);float lanes[32];
   for(unsigned l=0;l<32;++l)lanes[l]=row<p60::L?lane<iq3::Type::Q8_0>(b.low_w+row*iq3::expanded::row_bytes(iq3::Type::Q8_0,p60::K),b,inv[part],regenerate,bounds.first,bounds.second,l):lane<iq3::Type::F32>(b.inject_w+(row-p60::L)*p60::K*4,b,inv[part],regenerate,bounds.first,bounds.second,l);
   partial[part]=iq3::tree32(lanes);if(row>=p60::L)b.workspace[(row-p60::L)*8+part]=partial[part];
  }
  float value=(partial[0]+partial[1])+(partial[2]+partial[3]);
  if(row<p60::L)p60::low_output(b,row,value);else b.inject[row-p60::L]=iq3::bf16_bits(value);
 }
}
#ifndef OWN_RT_HOST_ONLY
inline sycl::event device(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&deps){
 const size_t rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,p60::K);
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((p60::L+p60::S)*128,128)](sycl::handler& h){
  sycl::local_accessor<float,1> partial(132,h),inverse(4,h);
  sycl::local_accessor<uint32_t,1> control(1,h);
  h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned local=it.get_local_linear_id(),part=local/32,lane_id=local%32,row=it.get_group_linear_id();auto sg=it.get_sub_group();
   if(!local){control[0]=uint32_t(*b.active&&!p60::failed(b)&&*b.position<b.capacity);if(!row&&*b.active&&!p60::failed(b)&&*b.position>=b.capacity)p60::fail(b);}
   it.barrier(sycl::access::fence_space::local_space);
   bool regenerate=control[0]!=0;
   if(regenerate){
    for(unsigned stream=0;stream<4;++stream){
     for(unsigned c=part;c<80;c+=4){float x=p60::get(b.x,stream*p60::H+c*32+lane_id);float sum=p60::tree(sg,x*x);if(!lane_id){partial[c]=sum;if(!row)b.scratch[stream*80+c]=sum;}}
     if(local>=80)partial[local]=0.f;
     it.barrier(sycl::access::fence_space::local_space);
     float upper=p60::tree(sg,partial[local]);if(!lane_id)partial[128+part]=upper;
     it.barrier(sycl::access::fence_space::local_space);
     if(!local){float total=(partial[128]+partial[129])+(partial[130]+partial[131]);inverse[stream]=detmath::rsqrt(total/float(p60::H)+1e-6f);}
     it.barrier(sycl::access::fence_space::local_space);
    }
    // Unique writer for downstream mix/snapshots. Other groups never read it.
    if(!row)for(unsigned k=local;k<p60::K;k+=128)b.norm[k]=input(b,k,inverse[k/p60::H],true);
   }
   float inv=regenerate?inverse[part]:0.f;auto bounds=iq3::kopt2::bounds(p60::K,part,4);
   float value=row<p60::L?lane<iq3::Type::Q8_0>(b.low_w+row*rb,b,inv,regenerate,bounds.first,bounds.second,lane_id):lane<iq3::Type::F32>(b.inject_w+(row-p60::L)*p60::K*4,b,inv,regenerate,bounds.first,bounds.second,lane_id);
   value=p60::tree(sg,value);if(!lane_id){partial[part]=value;if(row>=p60::L)b.workspace[(row-p60::L)*8+part]=value;}
   it.barrier(sycl::access::fence_space::local_space);
   if(!local){uint16_t y=iq3::bf16_bits((partial[0]+partial[1])+(partial[2]+partial[3]));
    if(row<p60::L){b.low[row]=y;if(*b.active&&!p60::failed(b)&&*b.position<b.capacity)b.act[row]=p39::hc_activation(y);}else b.inject[row-p60::L]=y;
   }
  }));
 });
}
#endif
}
