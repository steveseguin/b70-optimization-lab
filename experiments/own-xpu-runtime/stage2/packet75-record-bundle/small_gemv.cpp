#include "small_gemv.hpp"
#include "mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace packet27::small {
namespace {
using namespace iq3;
struct Pointers {const uint8_t* w;const uint16_t* x;uint16_t* y;};
template<Type T,unsigned Rows,unsigned Cols,unsigned Variant> struct Member {
 static constexpr unsigned rows=Rows,cols=Cols,variant=Variant;
 static constexpr unsigned splits=Variant==1||Variant==4||Variant==7?4:1;
 static constexpr unsigned groups=(Rows*splits+3)/4;
 static constexpr Type type=T;
 static size_t row_bytes(){return integrated::arithmetic::row_bytes(T,Cols,Variant);}
 static float lane(const uint8_t* w,const uint16_t* x,unsigned part,unsigned l){
  const auto bounds=kopt2::bounds(Cols,part,splits);
  if constexpr(Variant==6||Variant==7)return expanded::lane(T,w,x,Type::BF16,Cols,bounds.first,bounds.second,l);
  else if constexpr(Variant==0||Variant==1)return kopt2::lane_range<T>(w,x,Type::BF16,bounds.first,bounds.second,l);
  else return kopt3::dot<T>(w,x,Type::BF16,bounds.first,bounds.second,l,kopt3::ConstantTables{},kopt3::HostShare{});
 }
#ifdef OWN_RT_HOST_ONLY
 static void host(Pointers p){packet24::mock_items(Rows,[&](size_t row){float parts[splits]{};
  for(unsigned part=0;part<splits;++part){float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=lane(p.w+row*row_bytes(),p.x,part,l);parts[part]=tree32(lanes);}
  float value=parts[0];if constexpr(splits==4)value=(parts[0]+parts[1])+(parts[2]+parts[3]);p.y[row]=bf16_bits(value);
 });}
#endif
#ifndef OWN_RT_HOST_ONLY
 static void device(Pointers p,unsigned group,sycl::nd_item<1> it,float* scratch,size_t rb){
  auto sg=it.get_sub_group();const unsigned l=sg.get_local_linear_id(),sub=sg.get_group_linear_id();
  const unsigned row=group*(4/splits)+sub/splits,part=sub%splits;
  float sum=0;if(row<Rows)sum=lane(p.w+row*rb,p.x,part,l);
  for(unsigned width=1;width<32;width*=2){float other=sycl::select_from_group(sg,sum,(l+width)%32);if(l%(2*width)==0)sum=sum+other;}
  if constexpr(splits==4){if(l==0)scratch[sub]=sum;it.barrier(sycl::access::fence_space::local_space);if(sub==0&&l==0)sum=(scratch[0]+scratch[1])+(scratch[2]+scratch[3]);}
  if(row<Rows&&l==0&&part==0)p.y[row]=bf16_bits(sum);
 }
#endif
};
// Empty member never forms an allocation or a workgroup.
struct Empty {static constexpr unsigned groups=0;};
using HLow=Member<Type::Q8_0,320,10240,7>;
using HInject=Member<Type::F32,4,10240,4>;
using AB=Member<Type::F32,48,2560,4>;
using Router=Member<Type::F32,512,2560,4>;
using Shared=Member<Type::F32,1,2560,4>;
using GateQ6=Member<Type::Q6_K,640,2560,7>;
using GateQ8=Member<Type::Q8_0,640,2560,6>;
// Mini retains its registered constant SG32 arithmetic, with literal geometry.
using MiniLow=Member<Type::F32,4,64,2>;using MiniInject=Member<Type::F32,4,64,2>;
using MiniAB=Member<Type::F32,3,16,2>;using MiniRouter=Member<Type::F32,16,16,2>;
using MiniGate=Member<Type::F32,8,16,2>;using MiniShared=Member<Type::F32,1,16,2>;
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
template<class A,class B,class C=Empty,class D=Empty> struct Tuple final:Base {
 static constexpr unsigned members=C::groups?4:2;
 static constexpr unsigned count=A::groups+B::groups+C::groups+D::groups;
 static Pointers bind(std::span<void*const> p,unsigned member){return {static_cast<const uint8_t*>(p[3*member]),static_cast<const uint16_t*>(p[3*member+1]),static_cast<uint16_t*>(p[3*member+2])};}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{A::host(bind(p,0));B::host(bind(p,1));if constexpr(C::groups){C::host(bind(p,2));D::host(bind(p,3));}}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const auto a=bind(p,0),b=bind(p,1);Pointers c{},d{};size_t crb=0,drb=0;
  if constexpr(C::groups){c=bind(p,2);d=bind(p,3);crb=C::row_bytes();drb=D::row_bytes();}
  const size_t arb=A::row_bytes(),brb=B::row_bytes();
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> partial(4,h);
   h.parallel_for(sycl::nd_range<1>(count*128,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned group=it.get_group_linear_id();auto scratch=partial.get_multi_ptr<sycl::access::decorated::no>().get();
    // Every workgroup takes one compile-time member body. No lane-loop dispatch.
    if(group<A::groups)A::device(a,group,it,scratch,arb);
    else if(group<A::groups+B::groups)B::device(b,group-A::groups,it,scratch,brb);
    else if constexpr(C::groups){if(group<A::groups+B::groups+C::groups)C::device(c,group-A::groups-B::groups,it,scratch,crb);else D::device(d,group-A::groups-B::groups-C::groups,it,scratch,drb);}
   });
  });
 }
#endif
};
template<class F> decltype(auto) choose(std::string_view name,F f){
 if(name=="small.hc")return f.template operator()<Tuple<HLow,HInject>>();
 if(name=="small.gdn.ab")return f.template operator()<Tuple<AB,AB>>();
 if(name=="small.ffn.q6")return f.template operator()<Tuple<Router,GateQ6,GateQ6,Shared>>();
 if(name=="small.ffn.q8")return f.template operator()<Tuple<Router,GateQ8,GateQ8,Shared>>();
 if(name=="small.mini.hc")return f.template operator()<Tuple<MiniLow,MiniInject>>();
 if(name=="small.mini.gdn.ab")return f.template operator()<Tuple<MiniAB,MiniAB>>();
 if(name=="small.mini.ffn")return f.template operator()<Tuple<MiniRouter,MiniGate,MiniGate,MiniShared>>();
 throw std::invalid_argument("unknown compile-time GEMV tuple");
}
template<class T> struct TupleShapes;
template<class A,class B,class C,class D>struct TupleShapes<Tuple<A,B,C,D>> {
 static std::vector<Shape> get(){std::vector<Shape> result{{A::type,A::rows,A::cols,A::variant},{B::type,B::rows,B::cols,B::variant}};if constexpr(C::groups){result.push_back({C::type,C::rows,C::cols,C::variant});result.push_back({D::type,D::rows,D::cols,D::variant});}return result;}
};
}
std::vector<std::string> names(){return {"small.hc","small.gdn.ab","small.ffn.q6","small.ffn.q8","small.mini.hc","small.mini.gdn.ab","small.mini.ffn"};}
std::vector<Shape> shapes(std::string_view name){return choose(name,[]<class T>{return TupleShapes<T>::get();});}
void validate(ownrt::Device& d,std::string_view name,std::span<const integrated::Matrix> ms,std::span<const unsigned> variants){
 const auto expected=shapes(name);if(ms.size()!=expected.size()||variants.size()!=expected.size())throw std::invalid_argument("small GEMV tuple member count");
 std::vector<std::pair<uint64_t,bool>> accesses;
 for(size_t i=0;i<ms.size();++i){const auto& m=ms[i];const auto& e=expected[i];
  if(m.type!=e.type||m.rows!=e.rows||m.columns!=e.columns||variants[i]!=e.variant||m.experts!=1||m.count!=1||m.routes||m.status||m.fp32||(m.span&&m.span!=m.rows)||m.activation!=iq3::Type::BF16||m.output_type!=iq3::Type::BF16)throw std::invalid_argument("small GEMV tuple geometry/format/arithmetic");
  for(auto [id,n,write]:{std::tuple{m.w,size_t(m.rows)*integrated::arithmetic::row_bytes(m.type,m.columns,variants[i]),false},std::tuple{m.x,size_t(m.columns)*2,false},std::tuple{m.y,size_t(m.rows)*2,true}}){const auto& r=d.arena.row(id);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<n||reinterpret_cast<uintptr_t>(r.pointer)%16)throw std::invalid_argument("small GEMV tuple extent/alignment");accesses.emplace_back(id,write);}
 }
 iq3::kopt3::validate_aliases(accesses);
}
integrated::Launch submit(ownrt::Device& d,std::string_view name,std::span<const integrated::Matrix> ms,std::span<const unsigned> variants){
 validate(d,name,ms,variants);std::array<ownrt::Allocation,12> ids{};size_t count=0;for(const auto& m:ms){ids[count++]=m.w;ids[count++]=m.x;ids[count++]=m.y;}
 return choose(name,[&]<class T>{T op;auto e=d.compute(op,std::span<const ownrt::Allocation>(ids.data(),count),{});return integrated::Launch{e,e,1};});
}
}
