#include "expert_down.hpp"
#include "p28/submit.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p29 {
using integrated::Matrix;using integrated::Launch;
void validate(ownrt::Device& d,const std::vector<Matrix>& m,const std::string& name,bool shared,unsigned variant){
 if(name!="p29.down.wg32"&&name!="p29.down.rows4")throw std::invalid_argument("p29 down name");
 if(m.size()!=1||m[0].type!=iq3::Type::IQ4_NL||m[0].columns!=640||m[0].rows!=2560||shared||variant!=2)throw std::invalid_argument("p29 down fixed 2560x640 single projection");
 p28::validate(d,m,"p28.private.wg32",shared,variant);
}
template<unsigned RowsPerGroup> struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 unsigned experts=512;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto routes=static_cast<const iq3::Route*>(p[3]);auto status=static_cast<uint32_t*>(p[4]);
  for(unsigned slot=0;slot<10;++slot){auto r=routes[slot];bool valid=iq3::valid_route(r,experts,2560,2560);status[slot]=!valid;
   #pragma omp parallel for num_threads(2) schedule(static)
   for(unsigned row=0;row<2560;++row){float lanes[32]{};if(valid&&row<r.row_count){unsigned source=(r.expert_id*2560+r.row_begin+row)*360;for(unsigned lane=0;lane<32;++lane)lanes[lane]=down_lane(w+source,x+slot*640,lane);}y[slot*2560+row]=iq3::bf16_bits(valid&&row<r.row_count?iq3::tree32(lanes):iq3::bits_float(0x7fc00000));}
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto routes=static_cast<const iq3::Route*>(p[3]);auto status=static_cast<uint32_t*>(p[4]);
  constexpr unsigned wg=32*RowsPerGroup,groups=25600/RowsPerGroup;const unsigned expert_count=experts;
  auto sizes=q.get_device().get_info<sycl::info::device::sub_group_sizes>();if(std::find(sizes.begin(),sizes.end(),32)==sizes.end()||q.get_device().get_info<sycl::info::device::max_work_group_size>()<wg)throw std::invalid_argument("p29 SG32 geometry");
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(groups*wg,wg),p28::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const unsigned logical=unsigned(it.get_group_linear_id())*RowsPerGroup+unsigned(sg.get_group_linear_id());const unsigned slot=logical/2560,row=logical%2560;
   const auto route=routes[slot];const bool route_ok=iq3::valid_route(route,expert_count,2560,2560),valid=route_ok&&row<route.row_count;
   float sum=0;if(valid){const unsigned source=(route.expert_id*2560+route.row_begin+row)*360;sum=down_lane(w+source,x+slot*640,lane);}
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0){y[logical]=iq3::bf16_bits(valid?sum:iq3::bits_float(0x7fc00000));if(row==0)status[slot]=!route_ok;}
  }));});
 }
#endif
};
Launch submit(ownrt::Device& d,const std::vector<Matrix>& ms,const std::string& name,bool shared,unsigned variant){validate(d,ms,name,shared,variant);const auto& m=ms[0];std::array<ownrt::Allocation,5> args{m.w,m.x,m.y,m.routes,m.status};auto issue=[&]<unsigned R>(){Kernel<R> k;k.experts=m.experts;auto e=d.compute(k,args,{});return Launch{e,e,1};};return name.ends_with("rows4")?issue.template operator()<4>():issue.template operator()<1>();}
}
