#include "p33_submit.hpp"
#include "p33_candidates.hpp"
#include "expert_down.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p33 {
template<unsigned Mode,iq3::Type T,unsigned K,unsigned Split=1> struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 p28::Bound b{};
 p28::Bound bind(std::span<void*const> p)const {auto d=b;d.w=static_cast<const uint8_t*>(p[0]);d.peer=static_cast<const uint8_t*>(p[1]);d.x=static_cast<const uint16_t*>(p[2]);d.y=static_cast<uint16_t*>(p[3]);d.py=static_cast<uint16_t*>(p[4]);d.routes=b.has_routes?static_cast<const iq3::Route*>(p[5]):nullptr;d.status=static_cast<uint32_t*>(p[6]);d.ps=static_cast<uint32_t*>(p[7]);d.scratch=static_cast<float*>(p[8]);return d;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto d=bind(p);
  for(unsigned slot=0;slot<d.count;++slot){
   auto r=d.routes?d.routes[slot]:iq3::Route{0,0,d.rows};
   bool ok=iq3::valid_route(r,d.experts,d.rows,d.rows);
   if(d.routes){d.status[slot]=!ok;if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S)d.ps[slot]=!ok;}
   #pragma omp parallel for num_threads(2) schedule(static) if(d.rows>=64)
   for(unsigned row=0;row<d.rows;++row){
    bool valid=ok&&row<r.row_count;float parts[2][4]{};
    for(unsigned part=0;part<Split;++part){
     float sums[2][32]{};auto range=iq3::kopt2::bounds(K,part,Split);
     if(valid)for(unsigned lane=0;lane<32;++lane){
      const unsigned source=(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb);
      if constexpr(T==iq3::Type::IQ4_NL)sums[0][lane]=down_lane<Mode,K>(d.w+source,d.x+slot*K,lane);
      else if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S){auto pair=expert_lane<T,K,true>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane);sums[0][lane]=pair[0];sums[1][lane]=pair[1];}
      else sums[0][lane]=dense_lane<T,K>(d.w+source,d.x,unsigned(range.first),unsigned(range.second),lane);
     }
     for(unsigned j=0;j<(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1);++j)parts[j][part]=iq3::tree32(sums[j]);
    }
    for(unsigned j=0;j<(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1);++j){float v=Split==1?parts[j][0]:(parts[j][0]+parts[j][1])+(parts[j][2]+parts[j][3]);(j?d.py:d.y)[slot*d.rows+row]=iq3::bf16_bits(valid?v:iq3::bits_float(0x7fc00000));}
   }
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto d=bind(p);
  const size_t groups=size_t(d.rows)*d.count*Split;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(groups*32,32),p28::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),item=unsigned(it.get_group_linear_id()),logical=item/Split,part=item%Split;
   const unsigned row=logical%d.rows,slot=logical/d.rows;
   iq3::Route r{0,0,d.rows};if(d.routes)r=d.routes[slot];const bool ok=iq3::valid_route(r,d.experts,d.rows,d.rows),valid=ok&&row<r.row_count;
   std::array<float,2> sums{};
   if(valid){const unsigned source=(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb);auto range=iq3::kopt2::bounds(K,part,Split);
    if constexpr(T==iq3::Type::IQ4_NL)sums[0]=down_lane<Mode,K>(d.w+source,d.x+slot*K,lane);
    else if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S)sums=expert_lane<T,K,true>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane);
    else sums[0]=dense_lane<T,K>(d.w+source,d.x,unsigned(range.first),unsigned(range.second),lane);
   }
   constexpr unsigned projections=T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1;
   for(unsigned j=0;j<projections;++j){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sums[j],(lane+width)%32);if(lane%(2*width)==0)sums[j]=sums[j]+rhs;}
    if(lane==0){float v=valid?sums[j]:iq3::bits_float(0x7fc00000);if constexpr(Split==1)(j?d.py:d.y)[logical]=iq3::bf16_bits(v);else d.scratch[(logical*2+j)*4+part]=v;}}
   if(lane==0&&row==0&&part==0&&d.routes){d.status[slot]=!ok;if constexpr(projections==2)d.ps[slot]=!ok;}
  }));});
 }
#endif
};
#ifndef OWN_RT_HOST_ONLY
struct Finish final:ownrt::SyclOperation {unsigned n;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto s=static_cast<const float*>(p[0]);auto y=static_cast<uint16_t*>(p[1]);unsigned count=n;return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(count),p28::checked([=](sycl::id<1> id){auto v=s+id[0]*8;y[id[0]]=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));}));});}
};
 #endif
template<unsigned Mode,iq3::Type T,unsigned K,unsigned Split> integrated::Launch issue(ownrt::Device& d,const std::vector<integrated::Matrix>& ms){
 const auto& m=ms[0];const auto& peer=ms.size()==2?ms[1]:m;Kernel<Mode,T,K,Split> k;
 k.b.rb=integrated::arithmetic::row_bytes(T,K,T==iq3::Type::F32||T==iq3::Type::BF16?(Split==4?4:0):(Split==4?7:(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0?6:2)));k.b.rows=m.rows;k.b.count=m.count;k.b.experts=m.experts;k.b.has_routes=bool(m.routes);
 if(uint64_t(m.experts)*m.rows*k.b.rb>UINT32_MAX)throw std::invalid_argument("p33 32-bit row offset overflow");
 std::array<ownrt::Allocation,9> ids{m.w,peer.w,m.x,m.y,peer.y,m.routes?m.routes:m.x,m.status?m.status:m.y,peer.status?peer.status:peer.y,m.workspace};auto e=d.compute(k,ids,{});integrated::Launch r{e,e,1};

#ifndef OWN_RT_HOST_ONLY
 if constexpr(Split==4){Finish f;f.n=m.rows*m.count;std::array a{m.workspace,m.y};std::array after{e};r.last=d.compute(f,a,after);r.passes=2;}
#endif
 return r;
}
template<iq3::Type T,unsigned K> integrated::Launch dense_issue(ownrt::Device& d,const std::vector<integrated::Matrix>& m,unsigned v){return v==7||v==4?issue<0,T,K,4>(d,m):issue<0,T,K,1>(d,m);}
template<iq3::Type T> integrated::Launch dense_shape(ownrt::Device& d,const std::vector<integrated::Matrix>& m,unsigned v){
 switch(m[0].columns){
 case 2560:return dense_issue<T,2560>(d,m,v);
 case 6144:return dense_issue<T,6144>(d,m,v);
 case 10240:return dense_issue<T,10240>(d,m,v);
 case 320:if constexpr(T!=iq3::Type::Q6_K)return dense_issue<T,320>(d,m,v);break;
 case 640:if constexpr(T!=iq3::Type::Q6_K)return dense_issue<T,640>(d,m,v);break;
 }throw std::invalid_argument("p33 dense uncompiled shape");
}
integrated::Launch submit(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const std::string& name,bool shared,unsigned variant){
 if(name=="p33.down.bank"||name=="p33.down.select"){
  p29::validate(d,m,"p29.down.wg32",shared,variant);
  return name=="p33.down.bank"?issue<0,iq3::Type::IQ4_NL,640,1>(d,m):issue<1,iq3::Type::IQ4_NL,640,1>(d,m);
 }
 if(name=="p33.gate.restrict"){
  p28::validate(d,m,"p28.paired.wg32",shared,variant);
  if(m[0].type==iq3::Type::IQ2_S)return issue<0,iq3::Type::IQ2_S,2560,1>(d,m);
  if(m[0].type==iq3::Type::IQ3_S)return issue<0,iq3::Type::IQ3_S,2560,1>(d,m);
 }
 if(name=="p33.dense.segment"){
  p28::validate(d,m,"p28.dense.wg32",shared,variant);
  switch(m[0].type){
   case iq3::Type::Q6_K:return dense_shape<iq3::Type::Q6_K>(d,m,variant);
   case iq3::Type::Q8_0:return dense_shape<iq3::Type::Q8_0>(d,m,variant);
   case iq3::Type::F32:return dense_shape<iq3::Type::F32>(d,m,variant);
   case iq3::Type::BF16:return dense_shape<iq3::Type::BF16>(d,m,variant);
   default:break;
  }
 }
 throw std::invalid_argument("p33 candidate/type/shape");
}
}
