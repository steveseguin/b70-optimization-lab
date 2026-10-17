#include "p69_head.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p69 {
template<unsigned WG>struct Head final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 unsigned rows;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);
  const size_t stride=row_bytes();
  for(unsigned r=0;r<rows;++r)y[r]=iq3::bf16_bits(row(w+size_t(r)*stride,x));
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);unsigned n=rows;
  const size_t stride=row_bytes();
  const size_t global=((size_t(n)*32+WG-1)/WG)*WG;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(global,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned id=sg.get_local_linear_id(),r=it.get_global_linear_id()/32;
   float sum=r<n?lane(w+size_t(r)*stride,x,id):0;
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(id+width)%32);if(id%(2*width)==0)sum=sum+rhs;}
   if(id==0&&r<n)y[r]=iq3::bf16_bits(sum);
  });});
 }
#endif
};
integrated::Launch head(ownrt::Device&d,const integrated::Matrix&m,const std::string&choice){
 if(m.type!=iq3::Type::Q6_K||m.columns!=2560||m.count!=1||m.experts!=1||m.routes||!m.rows||m.rows>248320)throw std::invalid_argument("packet69 head geometry");
 p28::validate(d,{m},"p28.dense.wg32",false,6);
 std::array<ownrt::Allocation,3>ids{m.w,m.x,m.y};ownrt::Event e;
 if(choice=="wide64"){Head<64>op;op.rows=m.rows;e=d.compute(op,ids,{});}
 else if(choice=="wide128"){Head<128>op;op.rows=m.rows;e=d.compute(op,ids,{});}
 else throw std::invalid_argument("packet69 head selection");
 return {e,e,1};
}
}
