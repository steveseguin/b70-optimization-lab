#include "submit.hpp"
#include "dense.hpp"
#include "expert.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
#include <algorithm>
namespace p28 {
using integrated::Matrix;using integrated::Launch;
void validate(ownrt::Device& d,const std::vector<Matrix>& ms,const std::string& name,bool shared,unsigned v){
 if(ms.empty()||ms.size()>2)throw std::invalid_argument("p28 matrix count");
 const auto& a=ms[0];if(a.type!=Type::Q6_K&&a.type!=Type::Q8_0&&a.type!=Type::F32&&a.type!=Type::BF16&&a.type!=Type::IQ2_S&&a.type!=Type::IQ3_S&&a.type!=Type::IQ4_NL)throw std::invalid_argument("p28 unsupported type");auto names=candidates(a.type);
 if(std::find(names.begin(),names.end(),name)==names.end())throw std::invalid_argument("p28 candidate/type");
 if(!a.rows||a.rows>248320||!a.columns||a.columns>17408||!a.count||a.count>10||!a.experts||a.experts>512||a.columns%iq3::layout(a.type).elements)throw std::invalid_argument("p28 geometry");
 bool routed=expert(a.type);
 const bool output_pair=a.type==Type::IQ2_S||a.type==Type::IQ3_S;
 if(routed&&(ms.size()!=(output_pair?2u:1u)||shared!=output_pair))throw std::invalid_argument("p28 expert projection cardinality");
 if(routed?(v!=2||!a.routes||(a.experts!=512&&a.experts!=10)||a.count!=10||shared!=(ms.size()==2)):(ms.size()!=1||shared||a.routes||a.status||a.count!=1||a.experts!=1))throw std::invalid_argument("p28 dense/routed contract");
 if(!routed&&(((a.type==Type::F32||a.type==Type::BF16) && v!=0&&v!=4)||(a.type!=Type::F32&&a.type!=Type::BF16&&v!=6&&v!=7)))throw std::invalid_argument("p28 arithmetic variant");
 if((a.type==Type::IQ4_NL&&a.columns!=640)||(routed&&a.type!=Type::IQ4_NL&&a.columns!=2560)||(!routed&&a.columns!=320&&a.columns!=640&&a.columns!=2560&&a.columns!=6144&&a.columns!=10240))throw std::invalid_argument("p28 uncompiled shape family");
 std::vector<std::pair<uint64_t,bool>> accesses;
 auto extent=[&](ownrt::Allocation id,size_t bytes,bool write){auto r=d.arena.row(id);if(!r.live||r.memory!=ownrt::Memory::device||bytes>r.bytes||reinterpret_cast<uintptr_t>(r.pointer)%16)throw std::invalid_argument("p28 extent/alignment");accesses.emplace_back(id,write);};
 for(const auto& m:ms){
  if(m.type!=a.type||m.rows!=a.rows||m.columns!=a.columns||m.count!=a.count||m.experts!=a.experts||m.routes!=a.routes||m.x!=a.x||(m.span&&m.span!=m.rows)||m.activation!=Type::BF16||m.output_type!=Type::BF16||m.fp32)throw std::invalid_argument("p28 matrix identity");
  extent(m.w,size_t(m.experts)*m.rows*integrated::arithmetic::row_bytes(m.type,m.columns,v),false);
  extent(m.x,size_t(shared?1:m.count)*m.columns*2,false);extent(m.y,size_t(m.count)*m.rows*2,true);
  if(routed){extent(m.routes,m.count*sizeof(iq3::Route),false);extent(m.status,m.count*4,true);}
 }
 extent(a.workspace,size_t(a.rows)*a.count*8*4,true);
 iq3::kopt3::validate_aliases(accesses);
}
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
   for(unsigned row=0;row<d.rows;++row){float partial[2][4]{};if(valid&&row<r.row_count){size_t source=size_t(r.expert_id)*d.rows+r.row_begin+row;for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float sums[2][32]{};for(unsigned l=0;l<32;++l){auto values=lanes<T,K,Shared,Paired>(d.w+source*d.rb,d.peer+source*d.rb,d.x+(OutputPair?0:size_t(slot)*K),bounds.first,bounds.second,l,iq3::kopt3::HostShare{});sums[0][l]=values[0];sums[1][l]=values[1];}for(unsigned j=0;j<(OutputPair?2u:1u);++j)partial[j][part]=iq3::tree32(sums[j]);}}
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
   if(valid){size_t source=size_t(r.expert_id)*d.rows+r.row_begin+row;auto range=iq3::kopt2::bounds(K,part,Split);values=lanes<T,K,Shared,Paired>(d.w+source*d.rb,d.peer+source*d.rb,d.x+(OutputPair?0:size_t(slot)*K),range.first,range.second,l,Share{sg,l});}
   for(unsigned j=0;j<(OutputPair?2u:1u);++j){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,values[j],(l+width)%32);if(l%(2*width)==0)values[j]=values[j]+rhs;}
    if(active&&l==0){if constexpr(Split==1)(j?d.py:d.y)[logical]=iq3::bf16_bits(valid?values[j]:iq3::bits_float(0x7fc00000));else {if constexpr(rpg==4)partial[((sub/Split)*2+j)*4+part]=valid?values[j]:iq3::bits_float(0x7fc00000);else d.scratch[(logical*2+j)*4+part]=valid?values[j]:iq3::bits_float(0x7fc00000);}}}
   if constexpr(rpg==4){it.barrier(sycl::access::fence_space::local_space);if(active&&l==0&&part==0&&Split==4){for(unsigned j=0;j<(OutputPair?2u:1u);++j){auto off=((sub/Split)*2+j)*4;(j?d.py:d.y)[logical]=iq3::bf16_bits((partial[off]+partial[off+1])+(partial[off+2]+partial[off+3]));}}}
   if(active&&l==0&&row==0&&part==0&&d.routes){d.status[slot]=!route_ok;if constexpr(OutputPair)d.ps[slot]=!route_ok;}
  }));});
 }
#endif
};
#ifndef OWN_RT_HOST_ONLY
template<bool OutputPair> struct Finish final:ownrt::SyclOperation {
 unsigned n;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  auto scratch=static_cast<const float*>(p[0]);auto y=static_cast<uint16_t*>(p[1]);auto py=static_cast<uint16_t*>(p[2]);auto rows=n;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(rows),checked([=](sycl::id<1> id){for(unsigned j=0;j<(OutputPair?2u:1u);++j){auto v=scratch+(id[0]*2+j)*4;(j?py:y)[id[0]]=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));}}));});
 }
};
#endif
template<Type T,unsigned K,unsigned Split> Launch typed_split(ownrt::Device& d,const std::vector<Matrix>& ms,const std::string& name,unsigned variant){
 constexpr bool OutputPair=T==Type::IQ2_S||T==Type::IQ3_S;
 const auto& m=ms[0];const auto& p=OutputPair?ms[1]:m;
 auto issue=[&]<unsigned RPG,bool Shared,bool Paired>(){Kernel<T,K,Split,RPG,Shared,Paired> op;op.b.rb=integrated::arithmetic::row_bytes(T,K,variant);op.b.rows=m.rows;op.b.count=m.count;op.b.experts=m.experts;op.b.has_routes=bool(m.routes);
  std::array<ownrt::Allocation,9> ids{m.w,p.w,m.x,m.y,p.y,m.routes?m.routes:m.x,m.status?m.status:m.y,p.status?p.status:p.y,m.workspace};auto e=d.compute(op,ids,{});Launch out{e,e,1};
#ifndef OWN_RT_HOST_ONLY
  if constexpr(Split==4&&RPG==1){Finish<OutputPair> f;f.n=m.rows*m.count;std::array args{m.workspace,m.y,p.y};out.last=d.compute(f,args,{});out.passes=2;}
#endif
  return out;
 };
 const bool four=name.ends_with("rows4");
 if constexpr(expert_format(T)){
  if(name.starts_with("p28.shared."))return four?issue.template operator()<4,true,false>():issue.template operator()<1,true,false>();
  if constexpr(OutputPair)if(name.starts_with("p28.paired."))return four?issue.template operator()<4,false,true>():issue.template operator()<1,false,true>();
 }
 return four?issue.template operator()<4,false,false>():issue.template operator()<1,false,false>();
}
template<Type T,unsigned K> Launch typed(ownrt::Device& d,const std::vector<Matrix>& ms,const std::string& name,unsigned variant){
 if constexpr(expert_format(T))return typed_split<T,K,1>(d,ms,name,variant);
 else {if(variant==7||variant==4)return typed_split<T,K,4>(d,ms,name,variant);return typed_split<T,K,1>(d,ms,name,variant);}
}
template<Type T> Launch select_k(ownrt::Device& d,const std::vector<Matrix>& m,const std::string& n,unsigned v){
 if constexpr(expert_format(T)){if constexpr(T==Type::IQ4_NL)return typed<T,640>(d,m,n,v);else return typed<T,2560>(d,m,n,v);}
 else {switch(m[0].columns){
 case 2560:return typed<T,2560>(d,m,n,v);
 case 6144:return typed<T,6144>(d,m,n,v);
 case 10240:return typed<T,10240>(d,m,n,v);
 case 320:if constexpr(T!=Type::Q6_K)return typed<T,320>(d,m,n,v);break;
 case 640:if constexpr(T!=Type::Q6_K)return typed<T,640>(d,m,n,v);break;
 }}throw std::invalid_argument("p28 uncompiled K");
}
Launch submit(ownrt::Device& d,const std::vector<Matrix>& m,const std::string& name,bool shared,unsigned v){validate(d,m,name,shared,v);
 switch(m[0].type){
#define CASE(T) case Type::T:return select_k<Type::T>(d,m,name,v)
 CASE(Q6_K);CASE(Q8_0);CASE(F32);CASE(BF16);CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);
#undef CASE
 default:throw std::invalid_argument("p28 uncompiled type");}
}
}
