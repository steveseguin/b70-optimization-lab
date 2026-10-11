#include "p25_bridge.hpp"
#ifdef OWN_RT_HOST_ONLY
#define HOST_ONLY
#endif
#include "p25_candidates.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace packet26::p25bridge {
using namespace integrated;using iq3::Type;
struct Bound {
 const uint8_t* w;const uint8_t* peer;const uint16_t* x;uint16_t* y;uint16_t* py;const iq3::Route* routes;uint32_t* status;uint32_t* peer_status;
 size_t rb;unsigned rows,k,count,experts,split;bool paired,shared,has_routes;
};
p25::C candidate(const std::string& name){
 if(name=="p25.rows4")return p25::C::rows4;if(name=="p25.scale8")return p25::C::scale8;if(name=="p25.wide8")return p25::C::wide8;
 if(name=="p25.wg32")return p25::C::wg32;if(name=="p25.private_decode")return p25::C::private_decode;if(name=="p25.paired_input")return p25::C::paired_input;
 throw std::invalid_argument("unlinked packet25 candidate: "+name);
}
#ifndef OWN_RT_HOST_ONLY
struct Share {sycl::sub_group sg;unsigned lane;template<class F>auto operator()(unsigned owner,F f)const{using R=decltype(f(owner));R v{};if(lane==owner)v=f(owner);return sycl::select_from_group(sg,v,owner);}};
struct Tables:iq3::kopt3::ConstantTables {sycl::sub_group sg;explicit Tables(sycl::sub_group s):sg(s){};int iq4(unsigned i)const{unsigned lane=sg.get_local_linear_id();int v=lane<16?iq3::kopt3::iq4_levels[lane]:0;return sycl::select_from_group(sg,v,i);}};
#endif
template<Type T,p25::C Variant>
struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 Bound host{};
 Bound bind(std::span<void*const> p)const{auto d=host;d.w=static_cast<const uint8_t*>(p[0]);d.peer=static_cast<const uint8_t*>(p[1]);d.x=static_cast<const uint16_t*>(p[2]);d.y=static_cast<uint16_t*>(p[3]);d.py=static_cast<uint16_t*>(p[4]);d.routes=host.has_routes?static_cast<const iq3::Route*>(p[5]):nullptr;d.status=static_cast<uint32_t*>(p[6]);d.peer_status=static_cast<uint32_t*>(p[7]);return d;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto d=bind(p);for(unsigned slot=0;slot<d.count;++slot){auto route=d.routes?d.routes[slot]:iq3::Route{0,0,d.rows};bool valid=iq3::valid_route(route,d.experts,d.rows,d.rows);if(d.routes){d.status[slot]=valid?0:1;if(d.paired)d.peer_status[slot]=valid?0:1;}
  for(unsigned row=0;row<d.rows;++row){std::array<float,2> value{iq3::bits_float(0x7fc00000),iq3::bits_float(0x7fc00000)};if(valid&&row<route.row_count){size_t source=size_t(route.expert_id)*d.rows+route.row_begin+row;value=p25::host_row<T,Variant>(d.w+source*d.rb,d.peer+source*d.rb,d.x+(d.shared?0:size_t(slot)*d.k),nullptr,nullptr,d.k,d.split,d.paired);}d.y[size_t(slot)*d.rows+row]=iq3::bf16_bits(value[0]);if(d.paired)d.py[size_t(slot)*d.rows+row]=iq3::bf16_bits(value[1]);}
 }}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto d=bind(p);unsigned rpg=p25::rows_per_group(Variant,d.split),wg=p25::local_size(Variant,d.split);size_t groups=(size_t(d.rows)*d.count+rpg-1)/rpg;
 return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> partial(rpg*2*d.split,h);
  h.parallel_for(sycl::nd_range<1>(groups*wg,wg),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id(),rr=sub/d.split,part=sub%d.split;size_t logical=it.get_group_linear_id()*rpg+rr;unsigned row=logical%d.rows,slot=logical/d.rows;bool active=rr<rpg&&logical<size_t(d.rows)*d.count;
   iq3::Route route{0,0,d.rows};if(active&&d.routes)route=d.routes[slot];bool valid=active&&iq3::valid_route(route,d.experts,d.rows,d.rows)&&row<route.row_count;std::array<float,2> value{};
   if(valid){size_t source=size_t(route.expert_id)*d.rows+route.row_begin+row;auto limits=iq3::kopt2::bounds(d.k,part,d.split);value=p25::lane<T,Variant>(d.w+source*d.rb,d.peer+source*d.rb,d.x+(d.shared?0:size_t(slot)*d.k),nullptr,nullptr,d.k,limits.first,limits.second,lane,d.paired,Tables(sg),Share{sg,lane});}
   for(unsigned projection=0;projection<(d.paired?2u:1u);++projection){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value[projection],(lane+width)%32);if(lane%(2*width)==0)value[projection]=value[projection]+rhs;}if(rr<rpg&&lane==0)partial[(rr*2+projection)*d.split+part]=value[projection];}
   it.barrier(sycl::access::fence_space::local_space);
   if(active&&lane==0&&part==0){for(unsigned projection=0;projection<(d.paired?2u:1u);++projection){auto off=(rr*2+projection)*d.split;float result=d.split==1?partial[off]:(partial[off]+partial[off+1])+(partial[off+2]+partial[off+3]);(projection?d.py:d.y)[logical]=iq3::bf16_bits(valid?result:iq3::bits_float(0x7fc00000));}if(d.routes&&row==0){auto status=iq3::valid_route(route,d.experts,d.rows,d.rows)?0:1;d.status[slot]=status;if(d.paired)d.peer_status[slot]=status;}}
  });});
 }
#endif
};
template<Type T> Launch submit_type(ownrt::Device& d,const std::vector<Matrix>& matrices,p25::C c,bool shared,unsigned variant){
 const auto& m=matrices[0];const auto& peer=matrices.size()==2?matrices[1]:m;
 auto selected=[&]<p25::C V>(){Kernel<T,V> op;op.host={nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,arithmetic::row_bytes(T,m.columns,variant),unsigned(m.rows),unsigned(m.columns),m.count,m.experts,variant==7?4u:1u,matrices.size()==2,shared,bool(m.routes)};std::array<ownrt::Allocation,8> a{m.w,peer.w,m.x,m.y,peer.y,m.routes?m.routes:m.x,m.status?m.status:m.y,peer.status?peer.status:peer.y};auto e=d.compute(op,a,{});return Launch{e,e,1};};
 switch(c){case p25::C::rows4:return selected.template operator()<p25::C::rows4>();case p25::C::wide8:return selected.template operator()<p25::C::wide8>();
 case p25::C::scale8:if constexpr(!p25::expert(T))return selected.template operator()<p25::C::scale8>();break;
 case p25::C::wg32:if constexpr(p25::expert(T))return selected.template operator()<p25::C::wg32>();break;
 case p25::C::private_decode:if constexpr(p25::expert(T))return selected.template operator()<p25::C::private_decode>();break;
 case p25::C::paired_input:if constexpr(p25::expert(T))return selected.template operator()<p25::C::paired_input>();break;
 default:break;}throw std::invalid_argument("candidate not valid for GEMV type");
}
Launch submit(ownrt::Device& d,const std::vector<Matrix>& m,const std::string& name,bool shared,unsigned variant){
 if(m.empty()||m.size()>2)throw std::invalid_argument("packet25 matrix count");if(!m[0].rows||!m[0].columns||!m[0].count||!m[0].experts||m[0].rows>248320||m[0].columns>17408||m[0].count>512||m[0].experts>512)throw std::invalid_argument("packet25 matrix geometry");auto t=m[0].type;auto c=candidate(name);auto registered=p25::candidates(t);if(std::find(registered.begin(),registered.end(),c)==registered.end())throw std::invalid_argument("packet25 candidate/type mismatch");
 // The bridge is an R5 overlay, not a new arithmetic selector. Packed stride
 // calculation truncates otherwise; reject incomplete quantization blocks.
 auto layout=iq3::layout(t);
 if(!layout.elements||m[0].columns%layout.elements)throw std::invalid_argument("packet25 incomplete quantization block");
 if(p25::expert(t)?variant!=2:(variant!=6&&variant!=7))throw std::invalid_argument("packet25 bridge requires registered R5 arithmetic");
 for(const auto& matrix:m){if(matrix.type!=t||matrix.rows!=m[0].rows||matrix.columns!=m[0].columns||matrix.count!=m[0].count||matrix.experts!=m[0].experts||matrix.x!=m[0].x||matrix.routes!=m[0].routes||(matrix.routes&&matrix.span&&matrix.span!=matrix.rows))throw std::invalid_argument("packet25 paired shape mismatch");auto rb=arithmetic::row_bytes(t,matrix.columns,variant);if(d.arena.row(matrix.w).bytes<size_t(matrix.experts)*matrix.rows*rb||d.arena.row(matrix.x).bytes<size_t(shared?1:matrix.count)*matrix.columns*2||d.arena.row(matrix.y).bytes<size_t(matrix.count)*matrix.rows*2)throw std::invalid_argument("packet25 binding extent");if(matrix.routes&&(d.arena.row(matrix.routes).bytes<size_t(matrix.count)*sizeof(iq3::Route)||!matrix.status||d.arena.row(matrix.status).bytes<size_t(matrix.count)*4))throw std::invalid_argument("packet25 route/status extent");}
 switch(t){
#define TYPE(T) case Type::T:return submit_type<Type::T>(d,m,c,shared,variant)
 TYPE(Q6_K);TYPE(Q8_0);TYPE(IQ2_S);TYPE(IQ3_S);TYPE(IQ3_XXS);TYPE(IQ4_NL);
#undef TYPE
 default:throw std::invalid_argument("packet25 unsupported type");}
}
}
