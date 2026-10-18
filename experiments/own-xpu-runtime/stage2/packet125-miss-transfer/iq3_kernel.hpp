// Exact production p28 Kernel/lanes/Share extraction; see build input pins.
#include "../packet58j-onecard-port/p28/submit.hpp"
#include "../packet58j-onecard-port/p28/dense.hpp"
#include "../packet58j-onecard-port/p28/expert.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
#include <algorithm>
namespace p28 {
using integrated::Matrix;using integrated::Launch;
#ifndef OWN_RT_HOST_ONLY
struct Share {sycl::sub_group sg;unsigned lane;template<class F>auto operator()(unsigned owner,F f)const{using R=decltype(f(owner));R v{};if(lane==owner)v=f(owner);return sycl::select_from_group(sg,v,owner);}};
#endif
template<Type T,unsigned K,bool Shared,bool Paired,class ShareFn>
inline std::array<float,2> lanes(const uint8_t* w,const uint8_t* peer,const uint16_t* x,unsigned begin,unsigned end,unsigned l,ShareFn share){
 if constexpr(expert_format(T)){
  if constexpr(Paired)return expert_lane<T,K,Shared,true>(w,peer,x,begin,end,l,ExpertByteTables{},share);
  auto v=expert_lane<T,K,Shared,false>(w,peer,x,begin,end,l,ExpertByteTables{},share);
  if constexpr(T==Type::IQ2_S||T==Type::IQ3_S)v[1]=expert_lane<T,K,Shared,false>(peer,w,x,begin,end,l,ExpertByteTables{},share)[0];return v;
 }else return {dense_lane<T,K>(w,x,begin,end,l),0};
}
template<Type T,unsigned K,unsigned Split,unsigned RowsPerGroup,bool Shared,bool Paired>
struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 static_assert(Split==1||Split==4);
 static_assert(!expert_format(T)||Split==1);
 static constexpr bool OutputPair=T==Type::IQ2_S||T==Type::IQ3_S;
 static_assert(!Paired||OutputPair);
 Bound b{};
 Bound bind(std::span<void*const> p)const{auto d=b;d.w=static_cast<const uint8_t*>(p[0]);d.peer=static_cast<const uint8_t*>(p[1]);d.x=static_cast<const uint16_t*>(p[2]);d.y=static_cast<uint16_t*>(p[3]);d.py=static_cast<uint16_t*>(p[4]);d.routes=b.has_routes?static_cast<const iq3::Route*>(p[5]):nullptr;d.status=static_cast<uint32_t*>(p[6]);d.ps=static_cast<uint32_t*>(p[7]);d.scratch=static_cast<float*>(p[8]);return d;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto d=bind(p);
  for(unsigned slot=0;slot<d.count;++slot){auto r=d.routes?d.routes[slot]:iq3::Route{0,0,d.rows};bool valid=iq3::valid_route(r,d.experts,d.rows,d.rows);if(d.routes){d.status[slot]=!valid;if constexpr(OutputPair)d.ps[slot]=!valid;}
   #pragma omp parallel for num_threads(2) schedule(static) if(d.rows>=64)
   for(unsigned row=0;row<d.rows;++row){float partial[2][4]{};if(valid&&row<r.row_count){size_t source=size_t(r.expert_id)*d.rows+r.row_begin+row;for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float sums[2][32]{};for(unsigned l=0;l<32;++l){auto values=lanes<T,K,Shared,Paired>(p58::resolve(d.w,source*d.rb,size_t(d.rows)*d.rb,d.indirect),p58::resolve(d.peer,source*d.rb,size_t(d.rows)*d.rb,d.indirect),d.x+(OutputPair?0:size_t(slot)*K),bounds.first,bounds.second,l,iq3::kopt3::HostShare{});sums[0][l]=values[0];sums[1][l]=values[1];}for(unsigned j=0;j<(OutputPair?2u:1u);++j)partial[j][part]=iq3::tree32(sums[j]);}}
    for(unsigned j=0;j<(OutputPair?2u:1u);++j){float v=Split==1?partial[j][0]:(partial[j][0]+partial[j][1])+(partial[j][2]+partial[j][3]);(j?d.py:d.y)[size_t(slot)*d.rows+row]=iq3::bf16_bits(valid&&row<r.row_count?v:iq3::bits_float(0x7fc00000));}
   }
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  auto d=bind(p);constexpr unsigned rpg=RowsPerGroup;constexpr unsigned wg=32*rpg*(rpg==4?Split:1);size_t items=size_t(d.rows)*d.count*(rpg==4?1:Split);size_t groups=(items+rpg-1)/rpg;auto sizes=q.get_device().get_info<sycl::info::device::sub_group_sizes>();if(std::find(sizes.begin(),sizes.end(),32)==sizes.end()||q.get_device().get_info<sycl::info::device::max_work_group_size>()<wg)throw std::invalid_argument("p28 SG32/work-group geometry unsupported");
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> partial(4*2*4,h);h.parallel_for(sycl::nd_range<1>(groups*wg,wg),checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id(),sub=sg.get_group_linear_id();size_t item=it.get_group_linear_id()*rpg*(rpg==4?Split:1)+sub,logical=item/Split;unsigned part=item%Split,row=logical%d.rows,slot=logical/d.rows;bool active=logical<size_t(d.rows)*d.count;
   iq3::Route r{0,0,d.rows};if(active&&d.routes)r=d.routes[slot];bool route_ok=active&&iq3::valid_route(r,d.experts,d.rows,d.rows);bool valid=route_ok&&row<r.row_count;
   std::array<float,2> values{};
   if(valid){size_t source=size_t(r.expert_id)*d.rows+r.row_begin+row;auto range=iq3::kopt2::bounds(K,part,Split);values=lanes<T,K,Shared,Paired>(p58::resolve(d.w,source*d.rb,size_t(d.rows)*d.rb,d.indirect),p58::resolve(d.peer,source*d.rb,size_t(d.rows)*d.rb,d.indirect),d.x+(OutputPair?0:size_t(slot)*K),range.first,range.second,l,Share{sg,l});}
   for(unsigned j=0;j<(OutputPair?2u:1u);++j){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,values[j],(l+width)%32);if(l%(2*width)==0)values[j]=values[j]+rhs;}
    if(active&&l==0){if constexpr(Split==1)(j?d.py:d.y)[logical]=iq3::bf16_bits(valid?values[j]:iq3::bits_float(0x7fc00000));else {if constexpr(rpg==4)partial[((sub/Split)*2+j)*4+part]=valid?values[j]:iq3::bits_float(0x7fc00000);else d.scratch[(logical*2+j)*4+part]=valid?values[j]:iq3::bits_float(0x7fc00000);}}}
   if constexpr(rpg==4){it.barrier(sycl::access::fence_space::local_space);if(active&&l==0&&part==0&&Split==4){for(unsigned j=0;j<(OutputPair?2u:1u);++j){auto off=((sub/Split)*2+j)*4;(j?d.py:d.y)[logical]=iq3::bf16_bits((partial[off]+partial[off+1])+(partial[off+2]+partial[off+3]));}}}
   if(active&&l==0&&row==0&&part==0&&d.routes){d.status[slot]=!route_ok;if constexpr(OutputPair)d.ps[slot]=!route_ok;}
  }));});
 }
#endif
};

}
