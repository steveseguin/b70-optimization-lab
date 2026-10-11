#include "kernels.hpp"
#include "sycl_operation.hpp"
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <algorithm>
#include <array>
#include <cassert>
#include <limits>
#include <set>
#include <sstream>
namespace iq3::kopt3 {
namespace {
std::string properties="null";
size_t mul(size_t a,size_t b){if(b && a>SIZE_MAX/b)throw std::overflow_error("extent");return a*b;}
void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes,size_t alignment=16) {
  const auto& r=d.arena.row(id);
  if(!bytes || !r.live || r.memory!=ownrt::Memory::device || bytes>r.bytes || reinterpret_cast<uintptr_t>(r.pointer)%alignment)
    throw std::invalid_argument("device extent/alignment");
}
void capture(sycl::queue& q) {
  if(properties!="null")return;
  auto d=q.get_device();auto sizes=d.get_info<sycl::info::device::sub_group_sizes>();
  if(std::find(sizes.begin(),sizes.end(),32)==sizes.end())throw std::invalid_argument("SG32 required");
  ze_device_properties_t z{};z.stype=ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
  auto rc=zeDeviceGetProperties(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d),&z);
  if(rc!=ZE_RESULT_SUCCESS)throw std::runtime_error("device properties query failed");
  std::ostringstream s;s<<"{\"max_compute_units\":"<<d.get_info<sycl::info::device::max_compute_units>()
    <<",\"max_work_group_size\":"<<d.get_info<sycl::info::device::max_work_group_size>()
    <<",\"local_mem_bytes\":"<<d.get_info<sycl::info::device::local_mem_size>()
    <<",\"global_mem_cache_line_bytes\":"<<d.get_info<sycl::info::device::global_mem_cache_line_size>()
    <<",\"threads_per_eu\":"<<z.numThreadsPerEU<<",\"eus_per_subslice\":"<<z.numEUsPerSubslice
    <<",\"subslices_per_slice\":"<<z.numSubslicesPerSlice<<",\"slices\":"<<z.numSlices<<",\"subgroup_sizes\":[";
  for(size_t i=0;i<sizes.size();++i)s<<(i?",":"")<<sizes[i];
  properties=s.str()+"],\"resident_occupancy\":\"not measured\"}";
}
struct Desc {
  Type type,a,o;size_t rows,k,rb,first,groups;uint32_t experts,count,span;
  unsigned w,x,y,r,status,fp,ws;bool routed,diagnostic;
};
struct DeviceShare {
  sycl::sub_group sg;unsigned lane;
  template<class F> auto operator()(unsigned owner,F f)const {
    using R=decltype(f(owner));R v{};if(lane==owner)v=f(owner);
    return sycl::select_from_group(sg,v,owner);
  }
};
struct SlmTables {
 const uint64_t* q2;const uint32_t* q3s;const uint32_t* q3;const int8_t* q4;
 uint64_t iq2(unsigned i)const{return q2[i];}
 uint32_t iq3s(unsigned i)const{return q3s[i];}
 uint32_t iq3(unsigned i)const{return q3[i];}
 int iq4(unsigned i)const{return q4[i];}
};
struct BroadcastTables:ConstantTables {
 sycl::sub_group sg;
 explicit BroadcastTables(sycl::sub_group s):sg(s){}
 int iq4(unsigned i)const {
   unsigned lane=sg.get_local_linear_id();int value=lane<16?iq4_levels[lane]:0;
   return sycl::select_from_group(sg,value,i);
 }
};
template<class Tables> float dispatch_dot(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t begin,size_t end,unsigned lane,Tables tables,DeviceShare share) {
#define CASE(T) case Type::T:return dot<Type::T>(w,x,a,begin,end,lane,tables,share)
 switch(t){CASE(F32);CASE(F16);CASE(BF16);CASE(Q8_0);CASE(Q6_K);CASE(Q3_K);CASE(IQ3_XXS);CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);}
#undef CASE
 return bits_float(0x7fc00000);
}
struct Multiply:ownrt::SyclOperation {
  std::array<Desc,8> desc{};unsigned count=0,split=1;size_t groups=0;bool reduce=false,slm=false;
  template<bool SLM> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto descriptors=desc;auto nm=count,ns=split;auto ng=groups;auto second=reduce;
    std::array<void*,64> ptr{};std::copy(p.begin(),p.end(),ptr.begin());
    return q.submit([&](sycl::handler& h){
      h.depends_on(deps);
      sycl::local_accessor<uint64_t,1> q2(SLM?1024:1,h);
      sycl::local_accessor<uint32_t,1> q3s(SLM?512:1,h),q3(SLM?256:1,h);
      sycl::local_accessor<int8_t,1> q4(SLM?16:1,h);
      h.parallel_for(sycl::nd_range<1>(ng*128,128),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        auto group=it.get_group_linear_id();auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
        unsigned which=0;for(unsigned j=1;j<nm;++j)if(group>=descriptors[j].first)which=j;
        auto d=descriptors[which];size_t task=(group-d.first)*4+sg.get_group_linear_id();
        if(second) {
          size_t total=size_t(d.count)*d.span;
          // One WI per output; load S in increasing order, then adjacent-pair tree.
          {
            size_t row=(group-d.first)*128+it.get_local_linear_id();
            if(row<total) {
              float values[4]{};
              for(unsigned s=0;s<ns;++s)values[s]=static_cast<const float*>(ptr[d.ws])[row*ns+s];
              for(unsigned width=1;width<ns;width*=2)for(unsigned s=0;s<ns;s+=width*2)values[s]=values[s]+values[s+width];
              float value=values[0];
              // Invalid slots/tails must retain the canonical NaN bits.
              if(d.routed){auto r=static_cast<const Route*>(ptr[d.r])[row/d.span];if(!valid_route(r,d.experts,d.rows,d.span)||row%d.span>=r.row_count)value=bits_float(0x7fc00000);}
              static_cast<uint16_t*>(ptr[d.y])[row]=output_bits(value,d.o);
              if(d.diagnostic)static_cast<float*>(ptr[d.fp])[row]=value;
            }
          }
          return;
        }
        // Only the table used by this workgroup's matrix is staged; once.
        if constexpr(SLM) {
          unsigned wi=it.get_local_linear_id();
          if(d.type==Type::IQ2_S)for(unsigned j=wi;j<1024;j+=128)q2[j]=iq2_s_grid[j];
          if(d.type==Type::IQ3_S)for(unsigned j=wi;j<512;j+=128)q3s[j]=iq3_s_grid[j];
          if(d.type==Type::IQ3_XXS)for(unsigned j=wi;j<256;j+=128)q3[j]=iq3_grid[j];
          if(d.type==Type::IQ4_NL && wi<16)q4[wi]=iq4_levels[wi];
          it.barrier(sycl::access::fence_space::local_space);
        }
        unsigned part=task%ns;size_t logical=task/ns;
        size_t slot=logical/d.span,row=logical%d.span;
        bool in_range=slot<d.count;Route r{0,0,uint32_t(d.rows)};
        if(d.routed && in_range)r=static_cast<const Route*>(ptr[d.r])[slot];
        bool valid=in_range && valid_route(r,d.experts,d.rows,d.span),active=valid && row<r.row_count;
        if(d.routed && in_range && row==0 && lane==0 && part==0)static_cast<uint32_t*>(ptr[d.status])[slot]=valid?0:1;
        float sum=0;
        if(active) {
          const auto w=static_cast<const uint8_t*>(ptr[d.w])+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb;
          const auto x=static_cast<const uint16_t*>(ptr[d.x])+slot*d.k;
          auto range=bounds(d.k,part,ns);DeviceShare share{sg,lane};
          if constexpr(SLM) {
            SlmTables tables{q2.template get_multi_ptr<sycl::access::decorated::no>().get(),q3s.template get_multi_ptr<sycl::access::decorated::no>().get(),q3.template get_multi_ptr<sycl::access::decorated::no>().get(),q4.template get_multi_ptr<sycl::access::decorated::no>().get()};
            sum=dispatch_dot(d.type,w,x,d.a,range.first,range.second,lane,tables,share);
          } else sum=dispatch_dot(d.type,w,x,d.a,range.first,range.second,lane,BroadcastTables(sg),share);
        }
        for(unsigned width=1;width<32;width*=2) {
          float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(width*2)==0)sum=sum+rhs;
        }
        if(lane==0 && in_range) {
          float value=active?sum:bits_float(0x7fc00000);
          if(ns>1)static_cast<float*>(ptr[d.ws])[logical*ns+part]=value;
          else {static_cast<uint16_t*>(ptr[d.y])[logical]=output_bits(value,d.o);if(d.diagnostic)static_cast<float*>(ptr[d.fp])[logical]=value;}
        }
      });
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    capture(q);
    if((slm?11280:17)>q.get_device().get_info<sycl::info::device::local_mem_size>() || q.get_device().get_info<sycl::info::device::max_work_group_size>()<128)
      throw std::invalid_argument("SLM/group device limit");
    return slm?run<true>(q,p,deps):run<false>(q,p,deps);
  }
};
}
std::string device_properties(){return properties;}
size_t workspace_bytes(size_t rows,unsigned count,Variant v){return mul(mul(mul(rows,count),splits(v)),4);}
Launch multiply(ownrt::Device& device,const std::vector<Matrix>& matrices,Variant variant) {
  if(matrices.empty() || matrices.size()>8)throw std::invalid_argument("1..8 matrices");
  Multiply op;op.count=matrices.size();op.split=splits(variant);op.slm=variant==Variant::slm || variant==Variant::slm_split4;
  std::vector<ownrt::Allocation> ids;std::vector<std::pair<uint64_t,bool>> accesses;
  for(unsigned i=0;i<matrices.size();++i) {
    auto m=matrices[i];auto l=layout(m.type);if(!m.span)m.span=m.rows;
    if(!l.elements || !m.rows || m.rows>UINT32_MAX || !m.columns || m.columns>17408 || m.columns%l.elements ||
      bool(m.routes)!=bool(m.status) || !m.experts || !m.count || !m.span || m.span>m.rows || (m.activation!=Type::BF16 && m.activation!=Type::F16) ||
      (m.output_type!=Type::BF16 && m.output_type!=Type::F16) || ((!m.routes || !m.status) && (m.experts!=1 || m.count!=1 || m.span!=m.rows)))
      throw std::invalid_argument("matrix geometry/type/routes");
    auto& d=op.desc[i];d={};d.type=m.type;d.a=m.activation;d.o=m.output_type;d.rows=m.rows;d.k=m.columns;d.rb=mul(m.columns/l.elements,l.bytes);
    d.first=op.groups;d.groups=(mul(mul(m.count,m.span),op.split)+3)/4;
    d.experts=m.experts;d.count=m.count;d.span=m.span;d.routed=m.routes!=0;d.diagnostic=m.fp32!=0;
    auto add=[&](ownrt::Allocation id,size_t n,bool write=false){accesses.emplace_back(id,write);check(device,id,n,id==m.w?64:16);unsigned index=ids.size();ids.push_back(id);return index;};
    d.w=add(m.w,mul(mul(m.experts,m.rows),d.rb));d.x=add(m.x,mul(mul(m.count,m.columns),2));d.y=add(m.y,mul(mul(m.count,m.span),2),true);
    if(d.routed){d.r=add(m.routes,mul(m.count,sizeof(Route)));d.status=add(m.status,mul(m.count,4),true);}
    if(d.diagnostic)d.fp=add(m.fp32,mul(mul(m.count,m.span),4),true);
    if(op.split>1)d.ws=add(m.workspace,workspace_bytes(m.span,m.count,variant),true);
    op.groups+=d.groups;
  }
  validate_aliases(accesses);
  auto first=device.compute(op,ids,{});if(op.split==1)return {first,first,1};
  op.reduce=true;op.groups=0;
  for(unsigned i=0;i<op.count;++i){auto& d=op.desc[i];d.first=op.groups;d.groups=(mul(d.count,d.span)+127)/128;op.groups+=d.groups;}
  std::array deps{first};auto last=device.compute(op,ids,deps);return {first,last,2};
}
}
namespace iq3::kopt3 {
Launch expert_gate_up(ownrt::Device& d,const Matrix& gate,const Matrix& up,Variant v) {
 if(splits(v)!=1 || !gate.routes || !up.routes || gate.count!=10 || up.count!=10 || gate.rows!=up.rows || gate.columns!=up.columns || gate.experts!=up.experts)
  throw std::invalid_argument("ten-expert gate/up geometry; one-pass variant required");
 return multiply(d,{gate,up},v);
}
Launch expert_down(ownrt::Device& d,const Matrix& down,Variant v) {
 if(splits(v)!=1 || !down.routes || down.count!=10)throw std::invalid_argument("ten-expert down; one-pass variant required");
 return multiply(d,{down},v);
}
Launch multiply_dispatched(ownrt::Device& d,const Matrix& m) {
 bool split=dispatch_split4(unsigned(m.type),m.rows,m.columns,m.experts);
 if(split){auto l=kopt2::multiply(d,{m},kopt2::Variant::split4);return {l.first,l.last,l.passes};}
 auto e=m.routes?kopt::routed_gemv(d,m.type,m.w,m.x,m.y,m.routes,m.status,m.experts,m.rows,m.columns,m.count,m.span,m.activation,m.output_type,32,m.fp32):kopt::gemv(d,m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,32,m.fp32);
 return {e,e,1};
}
}
