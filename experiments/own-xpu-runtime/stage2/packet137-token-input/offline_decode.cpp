// Offline-only compiler probe. No main, queue construction or device discovery.
#include <sycl/sycl.hpp>
#include "p93_head.hpp"
template<unsigned Mode> class Packet93OfflineHead;
template<unsigned Mode> sycl::event offline_head(sycl::queue& q,const uint8_t* w,const uint16_t* x,uint16_t* y){
 constexpr unsigned rows=248320,K=2560;
 return q.submit([&](sycl::handler& h){
  h.parallel_for<Packet93OfflineHead<Mode>>(sycl::nd_range<1>(size_t(rows)*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned row=it.get_group_linear_id(),lane=it.get_local_linear_id();auto sg=it.get_sub_group();float value;
   if constexpr(Mode==0)value=p33::dense_lane<iq3::Type::Q6_K,K>(w+size_t(row)*3380,x,0,K,lane);
   else if constexpr(Mode==1)value=p74::lane<iq3::Type::Q6_K,K>(w+size_t(row)*2100,x,0,K,lane);
   else value=p93::lane<Mode-1>(w,size_t(rows)*10,row,x,0,K,lane);
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
   if(!lane)y[row]=iq3::bf16_bits(value);
  });
 });
}
void packet93_offline_emit(sycl::queue& q,const uint8_t* w,const uint16_t* x,uint16_t* y){
 offline_head<0>(q,w,x,y);offline_head<1>(q,w,x,y);offline_head<2>(q,w,x,y);offline_head<3>(q,w,x,y);
}
