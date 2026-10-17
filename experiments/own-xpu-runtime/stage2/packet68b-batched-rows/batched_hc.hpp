#pragma once
#include "batched_rows.hpp"
#include "p60_kernels.hpp"
#include "p60_submit.hpp"
namespace p68b {
inline p60::Bound hc_bind(std::span<void*const>p,unsigned r,unsigned capacity){unsigned i=r*16;return {(const uint16_t*)p[i],(const float*)p[i+1],(const uint8_t*)p[i+2],(const uint8_t*)p[i+3],(const uint8_t*)p[i+4],(uint16_t*)p[i+5],(uint16_t*)p[i+6],(uint16_t*)p[i+7],(uint16_t*)p[i+8],(uint16_t*)p[i+9],(uint16_t*)p[i+10],(float*)p[i+11],(float*)p[i+12],(uint32_t*)p[i+13],(const uint32_t*)p[i+14],(const uint32_t*)p[i+15],capacity};}
template<int Stage>struct HCKernel final:Base {
 unsigned capacity=4096;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto a=hc_bind(p,0,capacity),b=hc_bind(p,1,capacity);
  if constexpr(Stage==0){p60::host_norm(a);p60::host_norm(b);}
  if constexpr(Stage==1){
   for(unsigned row=0;row<p60::L+p60::S;++row){auto y=row<p60::L?dense_host<Type::Q8_0>(a.low_w+row*iq3::expanded::row_bytes(Type::Q8_0,p60::K),a.norm,b.norm,p60::K,4):dense_host<Type::F32>(a.inject_w+(row-p60::L)*p60::K*4,a.norm,b.norm,p60::K,4);
    for(unsigned r=0;r<2;++r){auto c=r?b:a;if(row<p60::L){c.low[row]=y[r];if(p60::enabled(c))c.act[row]=p39::hc_activation(y[r]);}else {c.inject[row-p60::L]=y[r];p60::dot<Type::F32,p60::K,4>(c.inject_w+(row-p60::L)*p60::K*4,c.norm,c.workspace+(row-p60::L)*8);}}
   }
  }
  if constexpr(Stage==2){for(unsigned k=0;k<p60::H;++k){uint16_t gates[2][4];for(unsigned s=0;s<4;++s){unsigned row=s*p60::H+k;auto y=dense_host<Type::Q8_0>(a.gate_w+row*iq3::expanded::row_bytes(Type::Q8_0,p60::L),a.act,b.act,p60::L,1);for(unsigned r=0;r<2;++r){gates[r][s]=y[r];(r?b:a).gate[row]=y[r];}}p60::mix_output(a,k,gates[0]);p60::mix_output(b,k,gates[1]);}}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto a=hc_bind(p,0,capacity),b=hc_bind(p,1,capacity);
  const size_t low_stride=iq3::expanded::row_bytes(Type::Q8_0,p60::K),gate_stride=iq3::expanded::row_bytes(Type::Q8_0,p60::L);
  if constexpr(Stage==0){
   return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1> partial(264,h);sycl::local_accessor<uint32_t,1> control(2,h);
    h.parallel_for(sycl::nd_range<1>(40*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
     unsigned local=it.get_local_linear_id(),stream=it.get_group_linear_id()/10,tile=it.get_group_linear_id()%10,lane=local%32,group=local/32;auto sg=it.get_sub_group();
     if(local<2){auto c=local?b:a;control[local]=uint32_t(*c.active&&!p60::failed(c)&&*c.position<c.capacity);}it.barrier(sycl::access::fence_space::local_space);
     float inv[2]{};
     for(unsigned r=0;r<2;++r){auto c=r?b:a;unsigned off=r*132;
      for(unsigned chunk=group;chunk<80;chunk+=8){float x=p60::get(c.x,stream*p60::H+chunk*32+lane);float sum=tree(sg,x*x);if(!lane){partial[off+chunk]=sum;if(!tile&&control[r])c.scratch[stream*80+chunk]=sum;}}
      if(local>=80&&local<128)partial[off+local]=0.f;it.barrier(sycl::access::fence_space::local_space);
      float upper=local<128?partial[off+local]:0.f;upper=tree(sg,upper);if(!lane&&group<4)partial[off+128+group]=upper;it.barrier(sycl::access::fence_space::local_space);
      float total=(partial[off+128]+partial[off+129])+(partial[off+130]+partial[off+131]);inv[r]=detmath::rsqrt(total/float(p60::H)+1e-6f);
     }
     unsigned k=tile*256+local,i=stream*p60::H+k;float gain=a.gain[i]+0.f;
     if(control[0])a.norm[i]=iq3::bf16_bits((p60::get(a.x,i)*inv[0])*gain);
     if(control[1])b.norm[i]=iq3::bf16_bits((p60::get(b.x,i)*inv[1])*gain);
     if(!local&&!stream&&!tile){if(*a.active&&!p60::failed(a)&&*a.position>=a.capacity)p60::fail(a);if(*b.active&&!p60::failed(b)&&*b.position>=b.capacity)p60::fail(b);}
    });});
  }else if constexpr(Stage==1){
   return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1> partial(8,h);
    h.parallel_for(sycl::nd_range<1>((p60::L+p60::S)*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
     unsigned row=it.get_group_linear_id(),part=it.get_local_linear_id()/32,lane=it.get_local_linear_id()%32;auto bounds=iq3::kopt2::bounds(p60::K,part,4);
     auto v=row<p60::L?dense_lane<Type::Q8_0>(a.low_w+row*low_stride,a.norm,b.norm,p60::K,bounds.first,bounds.second,lane):dense_lane<Type::F32>(a.inject_w+(row-p60::L)*p60::K*4,a.norm,b.norm,p60::K,bounds.first,bounds.second,lane);
     for(unsigned r=0;r<2;++r){v[r]=tree(it.get_sub_group(),v[r]);if(!lane){partial[r*4+part]=v[r];if(row>=p60::L)(r?b:a).workspace[(row-p60::L)*8+part]=v[r];}}
     it.barrier(sycl::access::fence_space::local_space);
     if(!it.get_local_linear_id())for(unsigned r=0;r<2;++r){auto c=r?b:a;unsigned off=r*4;auto y=iq3::bf16_bits((partial[off]+partial[off+1])+(partial[off+2]+partial[off+3]));if(row<p60::L){c.low[row]=y;if(*c.active&&!p60::failed(c)&&*c.position<c.capacity)c.act[row]=p39::hc_activation(y);}else c.inject[row-p60::L]=y;}
    });});
  }else{
   return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<uint16_t,1> gates(16,h);
    h.parallel_for(sycl::nd_range<1>((p60::H/2)*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
     unsigned local=it.get_local_linear_id(),sub=local/32,lane=local%32,k=it.get_group_linear_id()*2+sub/4,stream=sub%4,row=stream*p60::H+k;
     auto v=dense_lane<Type::Q8_0>(a.gate_w+row*gate_stride,a.act,b.act,p60::L,0,p60::L,lane);
     for(unsigned r=0;r<2;++r){v[r]=tree(it.get_sub_group(),v[r]);if(!lane){auto y=iq3::bf16_bits(v[r]);(r?b:a).gate[row]=y;gates[r*8+sub]=y;}}
     it.barrier(sycl::access::fence_space::local_space);
     if(local<2)for(unsigned r=0;r<2;++r){auto c=r?b:a;if(*c.active&&!p60::failed(c)&&*c.position<c.capacity){unsigned out=it.get_group_linear_id()*2+local;float sum=0.f;for(unsigned s=0;s<4;++s)sum=sum+ng::sigmoid(p39::widen(gates[r*8+local*4+s]))*p60::get(c.norm,s*p60::H+out);c.mix[out]=iq3::bf16_bits(sum/4.f);}}
    });});
  }
 }
#endif
};
inline integrated::Launch hc(ownrt::Device&d,const p60::IDs&a,const p60::IDs&b,int stage,unsigned capacity){
 std::array<ownrt::Allocation,32>ids;std::copy(a.begin(),a.end(),ids.begin());std::copy(b.begin(),b.end(),ids.begin()+16);
 for(unsigned j:{1u,2u,3u,4u})if(a[j]!=b[j])throw std::invalid_argument("68b HC weights must be shared");
 const size_t bytes[]={p60::K*2,p60::K*4,p60::L*iq3::expanded::row_bytes(Type::Q8_0,p60::K),p60::K*iq3::expanded::row_bytes(Type::Q8_0,p60::L),p60::S*p60::K*4,p60::K*2,p60::L*2,p60::L*2,p60::K*2,p60::H*2,p60::S*2,320*4,32*4,4,4,4};
 for(unsigned r=0;r<2;++r)for(unsigned j=0;j<16;++j){auto id=ids[r*16+j];const auto&v=d.arena.row(id);if(!v.live||v.memory!=ownrt::Memory::device||v.bytes<bytes[j])throw std::invalid_argument("68b HC extent");}
 ownrt::Event e=0;
 if(stage==0){HCKernel<0>k;k.capacity=capacity;e=d.compute(k,ids,{});}else if(stage==1){HCKernel<1>k;k.capacity=capacity;e=d.compute(k,ids,{});}else if(stage==2){HCKernel<2>k;k.capacity=capacity;e=d.compute(k,ids,{});}else throw std::invalid_argument("68b HC stage");return {e,e,1};
}
}
