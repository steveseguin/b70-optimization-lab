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
 const uint8_t* w;const uint8_t* peer;const uint16_t* x;const float* xf;const float* scales;uint16_t* y;uint16_t* py;const iq3::Route* routes;uint32_t* status;uint32_t* peer_status;
 size_t rb;unsigned rows,k,count,experts,split;bool paired,shared,has_routes;
};
std::vector<std::string> alternatives(Type t){
 std::vector<std::string> out{"p25.rows4"};
 if(p25::expert(t)){out.insert(out.end(),{"p25.wg32","p25.private_decode"});if(t==Type::IQ4_NL)out.insert(out.end(),{"p25.wide8","p27.packed64","p27.rows2sg"});else out.insert(out.end(),{"p25.paired_input","p25.half_table"});}
 else out.insert(out.end(),{"p25.scale8","p25.wide8","p27.packed64"});
 out.push_back("p27.fp32_input");return out;
}
p25::C candidate(const std::string& name){
 if(name=="p27.fp32_input")return p25::C::fp32_input;if(name=="p27.packed64")return p25::C::packed64;if(name=="p27.rows2sg")return p25::C::rows2sg;
 if(name=="p25.half_table")return p25::C::half_table;
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
 Bound bind(std::span<void*const> p)const{auto d=host;d.w=static_cast<const uint8_t*>(p[0]);d.peer=static_cast<const uint8_t*>(p[1]);d.x=static_cast<const uint16_t*>(p[2]);d.y=static_cast<uint16_t*>(p[3]);d.py=static_cast<uint16_t*>(p[4]);d.routes=host.has_routes?static_cast<const iq3::Route*>(p[5]):nullptr;d.status=static_cast<uint32_t*>(p[6]);d.peer_status=static_cast<uint32_t*>(p[7]);d.xf=Variant==p25::C::fp32_input?static_cast<const float*>(p[8]):nullptr;d.scales=Variant==p25::C::half_table?static_cast<const float*>(p[9]):nullptr;return d;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto d=bind(p);for(unsigned slot=0;slot<d.count;++slot){auto route=d.routes?d.routes[slot]:iq3::Route{0,0,d.rows};bool valid=iq3::valid_route(route,d.experts,d.rows,d.rows);if(d.routes){d.status[slot]=valid?0:1;if(d.paired)d.peer_status[slot]=valid?0:1;}
  // CPU-only row parallelism: each row keeps its complete arithmetic tree.
  #pragma omp parallel for num_threads(2) schedule(static) if(d.rows>=64)
  for(unsigned row=0;row<d.rows;++row){std::array<float,2> value{iq3::bits_float(0x7fc00000),iq3::bits_float(0x7fc00000)};if(valid&&row<route.row_count){size_t source=size_t(route.expert_id)*d.rows+route.row_begin+row;value=p25::host_row<T,Variant>(d.w+source*d.rb,d.peer+source*d.rb,d.x+(d.shared?0:size_t(slot)*d.k),d.scales?d.scales+(size_t(slot)*d.rows+row)*(d.k/iq3::layout(T).elements):nullptr,d.scales&&d.paired?d.scales+(size_t(d.count)*d.rows+size_t(slot)*d.rows+row)*(d.k/iq3::layout(T).elements):nullptr,d.k,d.split,d.paired,d.xf?d.xf+(d.shared?0:size_t(slot)*d.k):nullptr);}d.y[size_t(slot)*d.rows+row]=iq3::bf16_bits(value[0]);if(d.paired)d.py[size_t(slot)*d.rows+row]=iq3::bf16_bits(value[1]);}
 }}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto d=bind(p);
 if constexpr(Variant==p25::C::rows2sg){
  // One physical half-subgroup owns a row. Its lanes keep two independent
  // virtual-lane sums; the high virtual lane has no third tile at K=640.
  size_t groups=(size_t(d.rows)*d.count+1)/2;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(groups*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned physical=sg.get_local_linear_id(),half=physical/16,lane=physical%16;size_t logical=it.get_group_linear_id()*2+half;bool active=logical<size_t(d.rows)*d.count;unsigned row=logical%d.rows,slot=logical/d.rows;iq3::Route route{0,0,d.rows};if(active&&d.routes)route=d.routes[slot];bool valid=active&&iq3::valid_route(route,d.experts,d.rows,d.rows)&&row<route.row_count;float sums[2]{};
   if(valid){size_t source=size_t(route.expert_id)*d.rows+route.row_begin+row;for(unsigned virtual_half=0;virtual_half<2;++virtual_half)sums[virtual_half]=p25::lane<T,p25::C::rows2sg>(d.w+source*d.rb,d.w+source*d.rb,d.x+(d.shared?0:size_t(slot)*d.k),nullptr,nullptr,d.k,0,d.k,lane+16*virtual_half,false,iq3::kopt3::ConstantTables{},iq3::kopt3::HostShare{})[0];}
   // Identical widths 1,2,4,8 separately in each virtual half; then width16.
   for(unsigned vh=0;vh<2;++vh)for(unsigned width=1;width<16;width*=2){float rhs=sycl::select_from_group(sg,sums[vh],half*16+(lane+width)%16);if(lane%(2*width)==0)sums[vh]=sums[vh]+rhs;}
   if(active&&lane==0){d.y[logical]=iq3::bf16_bits(valid?sums[0]+sums[1]:iq3::bits_float(0x7fc00000));if(d.routes&&row==0)d.status[slot]=iq3::valid_route(route,d.experts,d.rows,d.rows)?0:1;}
  });});
 }
 unsigned rpg=p25::rows_per_group(Variant,d.split),wg=p25::local_size(Variant,d.split);size_t groups=(size_t(d.rows)*d.count+rpg-1)/rpg;
 return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> partial(rpg*2*d.split,h);
  h.parallel_for(sycl::nd_range<1>(groups*wg,wg),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id(),rr=sub/d.split,part=sub%d.split;size_t logical=it.get_group_linear_id()*rpg+rr;unsigned row=logical%d.rows,slot=logical/d.rows;bool active=rr<rpg&&logical<size_t(d.rows)*d.count;
   iq3::Route route{0,0,d.rows};if(active&&d.routes)route=d.routes[slot];bool valid=active&&iq3::valid_route(route,d.experts,d.rows,d.rows)&&row<route.row_count;std::array<float,2> value{};
   if(valid){size_t source=size_t(route.expert_id)*d.rows+route.row_begin+row;auto limits=iq3::kopt2::bounds(d.k,part,d.split);value=p25::lane<T,Variant>(d.w+source*d.rb,d.peer+source*d.rb,d.x+(d.shared?0:size_t(slot)*d.k),d.scales?d.scales+logical*(d.k/iq3::layout(T).elements):nullptr,d.scales&&d.paired?d.scales+(size_t(d.count)*d.rows+logical)*(d.k/iq3::layout(T).elements):nullptr,d.k,limits.first,limits.second,lane,d.paired,Tables(sg),Share{sg,lane},d.xf?d.xf+(d.shared?0:size_t(slot)*d.k):nullptr);}
   for(unsigned projection=0;projection<(d.paired?2u:1u);++projection){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value[projection],(lane+width)%32);if(lane%(2*width)==0)value[projection]=value[projection]+rhs;}if(rr<rpg&&lane==0)partial[(rr*2+projection)*d.split+part]=value[projection];}
   it.barrier(sycl::access::fence_space::local_space);
   if(active&&lane==0&&part==0){for(unsigned projection=0;projection<(d.paired?2u:1u);++projection){auto off=(rr*2+projection)*d.split;float result=d.split==1?partial[off]:(partial[off]+partial[off+1])+(partial[off+2]+partial[off+3]);(projection?d.py:d.y)[logical]=iq3::bf16_bits(valid?result:iq3::bits_float(0x7fc00000));}if(d.routes&&row==0){auto status=iq3::valid_route(route,d.experts,d.rows,d.rows)?0:1;d.status[slot]=status;if(d.paired)d.peer_status[slot]=status;}}
  });});
 }
#endif
};
// Only the FP16 block scales of selected rows are prepared, never decoded
// weight values. Layout is [projection][route slot][output row][quant block].
template<Type T> struct ScalePreparation final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 unsigned rows=0,k=0,count=0,experts=0,projections=0;size_t rb=0;
 static float value(size_t index,const uint8_t* w,const uint8_t* peer,const iq3::Route* routes,unsigned rows,unsigned blocks,unsigned count,unsigned experts,size_t rb){
  size_t logical=index/blocks;unsigned block=index%blocks,row=logical%rows,slot=(logical/rows)%count,projection=logical/(size_t(rows)*count);
  auto route=routes?routes[slot]:iq3::Route{0,0,rows};
  if(!iq3::valid_route(route,experts,rows,rows)||row>=route.row_count)return 0.f;
  auto source=(projection?peer:w)+(size_t(route.expert_id)*rows+route.row_begin+row)*rb+size_t(block)*iq3::layout(T).bytes;
  return iq3::half(iq3::u16(source));
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{
  auto w=static_cast<const uint8_t*>(p[0]),peer=static_cast<const uint8_t*>(p[1]);auto routes=static_cast<const iq3::Route*>(p[2]);auto out=static_cast<float*>(p[3]);unsigned blocks=k/iq3::layout(T).elements;size_t n=size_t(projections)*count*rows*blocks;
  #pragma omp parallel for num_threads(2) schedule(static) if(n>=4096)
  for(size_t i=0;i<n;++i)out[i]=value(i,w,peer,routes,rows,blocks,count,experts,rb);
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  auto w=static_cast<const uint8_t*>(p[0]),peer=static_cast<const uint8_t*>(p[1]);auto routes=static_cast<const iq3::Route*>(p[2]);auto out=static_cast<float*>(p[3]);const auto r=rows,b=k/iq3::layout(T).elements,c=count,e=experts;const size_t stride=rb,n=size_t(projections)*c*r*b;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(n),[=](sycl::id<1> item){size_t i=item[0];out[i]=value(i,w,peer,routes,r,b,c,e,stride);});});
 }
#endif
};
template<Type T> Launch submit_type(ownrt::Device& d,const std::vector<Matrix>& matrices,p25::C c,bool shared,unsigned variant,ownrt::Allocation prepared_fp32){
 const auto& m=matrices[0];const auto& peer=matrices.size()==2?matrices[1]:m;
 auto selected=[&]<p25::C V>(){ownrt::Event first=0;
 if constexpr(V==p25::C::half_table){ScalePreparation<T> prep;prep.rows=m.rows;prep.k=m.columns;prep.count=m.count;prep.experts=m.experts;prep.projections=matrices.size();prep.rb=arithmetic::row_bytes(T,m.columns,variant);std::array<ownrt::Allocation,4> a{m.w,peer.w,m.routes,m.workspace};first=d.compute(prep,a,{});}
 Kernel<T,V> op;op.host={nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,arithmetic::row_bytes(T,m.columns,variant),unsigned(m.rows),unsigned(m.columns),m.count,m.experts,variant==7?4u:1u,matrices.size()==2,shared,bool(m.routes)};std::array<ownrt::Allocation,10> a{m.w,peer.w,m.x,m.y,peer.y,m.routes?m.routes:m.x,m.status?m.status:m.y,peer.status?peer.status:peer.y,prepared_fp32?prepared_fp32:m.x,V==p25::C::half_table?m.workspace:m.x};auto e=d.compute(op,a,{});return Launch{first?first:e,e,first?2u:1u};};
 switch(c){case p25::C::rows4:return selected.template operator()<p25::C::rows4>();case p25::C::wide8:return selected.template operator()<p25::C::wide8>();
 case p25::C::half_table:if constexpr(p25::expert(T)&&T!=Type::IQ4_NL)return selected.template operator()<p25::C::half_table>();break;
 case p25::C::fp32_input:return selected.template operator()<p25::C::fp32_input>();
 case p25::C::packed64:if constexpr(!p25::expert(T)||T==Type::IQ4_NL)return selected.template operator()<p25::C::packed64>();break;
 case p25::C::rows2sg:if constexpr(T==Type::IQ4_NL)return selected.template operator()<p25::C::rows2sg>();break;
 case p25::C::scale8:if constexpr(!p25::expert(T))return selected.template operator()<p25::C::scale8>();break;
 case p25::C::wg32:if constexpr(p25::expert(T))return selected.template operator()<p25::C::wg32>();break;
 case p25::C::private_decode:if constexpr(p25::expert(T))return selected.template operator()<p25::C::private_decode>();break;
 case p25::C::paired_input:if constexpr(p25::expert(T))return selected.template operator()<p25::C::paired_input>();break;
 default:break;}throw std::invalid_argument("candidate not valid for GEMV type");
}
Launch submit(ownrt::Device& d,const std::vector<Matrix>& m,const std::string& name,bool shared,unsigned variant,ownrt::Allocation prepared_fp32){
 if(m.empty()||m.size()>2)throw std::invalid_argument("packet25 matrix count");if(!m[0].rows||!m[0].columns||!m[0].count||!m[0].experts||m[0].rows>248320||m[0].columns>17408||m[0].count>512||m[0].experts>512)throw std::invalid_argument("packet25 matrix geometry");auto t=m[0].type;auto c=candidate(name);if(c==p25::C::rows2sg&&(m.size()!=1||m[0].columns!=640))throw std::invalid_argument("rows2sg requires single IQ4 K640 projection");auto registered=alternatives(t);if(std::find(registered.begin(),registered.end(),name)==registered.end())throw std::invalid_argument("packet25 candidate/type mismatch");
 if(c==p25::C::fp32_input&&(!prepared_fp32||d.arena.row(prepared_fp32).bytes<size_t(shared?1:m[0].count)*m[0].columns*4))throw std::invalid_argument("fp32 input requires prepared extent");
 // The bridge is an R5 overlay, not a new arithmetic selector. Packed stride
 // calculation truncates otherwise; reject incomplete quantization blocks.
 auto layout=iq3::layout(t);
 if(!layout.elements||m[0].columns%layout.elements)throw std::invalid_argument("packet25 incomplete quantization block");
 if(p25::expert(t)?variant!=2:(variant!=6&&variant!=7))throw std::invalid_argument("packet25 bridge requires registered R5 arithmetic");
 std::vector<std::pair<uint64_t,bool>> accesses;
 for(const auto& matrix:m){if((!matrix.routes&&(matrix.experts!=1||matrix.count!=1||matrix.status))||(matrix.routes&&matrix.count!=10))throw std::invalid_argument("packet27 dense/routed binding geometry");if(matrix.activation!=Type::BF16||matrix.output_type!=Type::BF16||matrix.fp32)throw std::invalid_argument("packet27 BF16 IO only, no diagnostic FP32 output");if(matrix.type!=t||matrix.rows!=m[0].rows||matrix.columns!=m[0].columns||matrix.count!=m[0].count||matrix.experts!=m[0].experts||matrix.x!=m[0].x||matrix.routes!=m[0].routes||(matrix.routes&&matrix.span&&matrix.span!=matrix.rows))throw std::invalid_argument("packet25 paired shape mismatch");auto rb=arithmetic::row_bytes(t,matrix.columns,variant);if(d.arena.row(matrix.w).bytes<size_t(matrix.experts)*matrix.rows*rb||d.arena.row(matrix.x).bytes<size_t(shared?1:matrix.count)*matrix.columns*2||d.arena.row(matrix.y).bytes<size_t(matrix.count)*matrix.rows*2)throw std::invalid_argument("packet25 binding extent");if(matrix.routes&&(d.arena.row(matrix.routes).bytes<size_t(matrix.count)*sizeof(iq3::Route)||!matrix.status||d.arena.row(matrix.status).bytes<size_t(matrix.count)*4))throw std::invalid_argument("packet25 route/status extent");accesses.insert(accesses.end(),{{matrix.w,false},{matrix.x,false},{matrix.y,true}});if(matrix.routes)accesses.insert(accesses.end(),{{matrix.routes,false},{matrix.status,true}});}
 if(c==p25::C::half_table){size_t bytes=size_t(m.size())*m[0].count*m[0].rows*(m[0].columns/layout.elements)*4;if(!m[0].routes||!m[0].workspace||d.arena.row(m[0].workspace).bytes<bytes)throw std::invalid_argument("half_table routed scale workspace extent");accesses.emplace_back(m[0].workspace,true);}
 if(c==p25::C::fp32_input)accesses.emplace_back(prepared_fp32,false);for(auto [id,write]:accesses){const auto& allocation=d.arena.row(id);if(!allocation.live||allocation.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(allocation.pointer)%16)throw std::invalid_argument("packet27 GEMV memory/alignment");}iq3::kopt3::validate_aliases(accesses);
 switch(t){
#define TYPE(T) case Type::T:return submit_type<Type::T>(d,m,c,shared,variant,prepared_fp32)
 TYPE(Q6_K);TYPE(Q8_0);TYPE(IQ2_S);TYPE(IQ3_S);TYPE(IQ3_XXS);TYPE(IQ4_NL);
#undef TYPE
 default:throw std::invalid_argument("packet25 unsupported type");}
}

struct Prepare final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{size_t n=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto x=static_cast<const uint16_t*>(p[0]);auto y=static_cast<float*>(p[1]);for(size_t i=0;i<n;++i)y[i]=iq3::bits_float(uint32_t(x[i])<<16);}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto x=static_cast<const uint16_t*>(p[0]);auto y=static_cast<float*>(p[1]);auto count=n;return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(count),[=](sycl::id<1> i){y[i]=iq3::bits_float(uint32_t(x[i])<<16);});});}
#endif
};
Launch prepare_input(ownrt::Device& d,ownrt::Allocation x,ownrt::Allocation y,size_t n){if(!n||n>174080||d.arena.row(x).bytes<n*2||d.arena.row(y).bytes<n*4)throw std::invalid_argument("fp32 prepare extent");if(x==y)throw std::invalid_argument("fp32 prepare must not alias input");for(auto id:{x,y}){const auto& row=d.arena.row(id);if(!row.live||row.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(row.pointer)%16)throw std::invalid_argument("fp32 prepare memory/alignment");}Prepare op;op.n=n;std::array<ownrt::Allocation,2>a{x,y};auto e=d.compute(op,a,{});return {e,e,1};}
}
