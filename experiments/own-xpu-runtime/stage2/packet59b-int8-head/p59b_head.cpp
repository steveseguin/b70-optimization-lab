#include "p59b_head.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p59b {
struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 unsigned rows,columns;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto w=static_cast<const int8_t*>(p[0]);auto scales=static_cast<const float*>(p[1]);auto x=static_cast<const uint16_t*>(p[2]);auto y=static_cast<uint16_t*>(p[3]);
  #pragma omp parallel for num_threads(2) schedule(static)
  for(unsigned r=0;r<rows;++r){float sums[32];for(unsigned l=0;l<32;++l)sums[l]=lane(w+size_t(r)*columns,x,columns,l);y[r]=iq3::bf16_bits(iq3::tree32(sums)*scales[r]);}
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto w=static_cast<const int8_t*>(p[0]);auto scales=static_cast<const float*>(p[1]);auto x=static_cast<const uint16_t*>(p[2]);auto y=static_cast<uint16_t*>(p[3]);auto nr=rows,k=columns;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((size_t(nr)+3)/4)*128,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id();size_t r=it.get_global_linear_id()/32;if(r>=nr)return;
   float sum=lane(w+r*k,x,k,l);
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(l+width)%32);if(l%(2*width)==0)sum=sum+rhs;}
   if(l==0)y[r]=iq3::bf16_bits(sum*scales[r]);
  });});
 }
#endif
};
integrated::Launch head(ownrt::Device& d,const Head& a) {
 if(!a.rows||a.rows>91392||!a.columns||a.columns>2560)throw std::invalid_argument("p59b head shape");
 std::array ids{a.codes,a.scales,a.x,a.y};std::array<size_t,4> sizes{size_t(a.rows)*a.columns,size_t(a.rows)*4,size_t(a.columns)*2,size_t(a.rows)*2};
 for(unsigned j=0;j<4;++j){const auto& r=d.arena.row(ids[j]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<sizes[j])throw std::invalid_argument("p59b head extent");}
 if(a.y==a.codes||a.y==a.scales||a.y==a.x)throw std::invalid_argument("p59b output alias");
 Kernel op;op.rows=a.rows;op.columns=a.columns;auto event=d.compute(op,ids,{});return {event,event,1};
}
}
