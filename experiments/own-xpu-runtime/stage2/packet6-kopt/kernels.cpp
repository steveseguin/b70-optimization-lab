#include "kernels.hpp"
#include "reference.hpp"
#include "sycl_operation.hpp"
#include <algorithm>
#include <array>
#include <limits>
#include <set>
#include <sstream>

namespace iq3::kopt {
namespace {
constexpr size_t rows_per_group=4;
std::string properties="null";
size_t mul(size_t a,size_t b) {
  if(b && a>std::numeric_limits<size_t>::max()/b)throw std::overflow_error("kopt extent");
  return a*b;
}
void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes) {
  auto& r=d.arena.row(id);
  if(!bytes || !r.live || r.memory!=ownrt::Memory::device || bytes>r.bytes)
    throw std::invalid_argument("kopt device binding extent");
  if(reinterpret_cast<uintptr_t>(r.pointer)%16)throw std::invalid_argument("kopt allocation must be aligned16");
}
void geometry(Type t,Type a,Type o,size_t rows,size_t k,unsigned sg) {
  auto l=layout(t);
  if(!l.elements || !rows || rows>UINT32_MAX || !k || k>16384 || k%l.elements ||
     (a!=Type::BF16 && a!=Type::F16) || (o!=Type::BF16 && o!=Type::F16) || (sg!=16 && sg!=32))
    throw std::invalid_argument("kopt geometry/type/subgroup");
}
struct Descriptor {
  Type type,activation,output;size_t rows,k,rb,first_group,groups;
  uint32_t experts,count,span;bool routed;
  unsigned w,x,y,r,status,fp32;bool diagnostic;
};
// A fully aligned interior is read exactly once in 16-byte chunks per row.
// Edges are scalar and bounded to that row. No block-start alignment fiction.
template<unsigned SG> inline void stage_row(const uint8_t* src,uint8_t* dst,size_t n,unsigned lane) {
  size_t prefix=(16-(reinterpret_cast<uintptr_t>(src)&15))&15;
  prefix=prefix<n?prefix:n;
  for(size_t i=lane;i<prefix;i+=SG)dst[i]=src[i];
  size_t vectors=(n-prefix)/16;
  auto aligned=reinterpret_cast<const sycl::vec<uint32_t,4>*>(src+prefix);
  for(size_t j=lane;j<vectors;j+=SG) {
    auto bytes=aligned[j].template as<sycl::vec<uint8_t,16>>();
    for(unsigned i=0;i<16;++i)dst[prefix+j*16+i]=bytes[i];
  }
  for(size_t i=prefix+vectors*16+lane;i<n;i+=SG)dst[i]=src[i];
}
template<Type T,unsigned SG> inline float dot(const uint8_t* row,const uint16_t* x,Type a,size_t k,unsigned lane) {
  if constexpr(layout(T).elements!=1)return lane_dot<T>(row,x,a,k,lane,SG);
  else {
    // Raw formats bypass SLM; consecutive lanes consume consecutive 16/32 B.
    float acc=0;
    for(size_t base=size_t(lane)*8;base<k;base+=SG*8) {
      float values[8];uint16_t inputs[8];
      if(base+8<=k && reinterpret_cast<uintptr_t>(row+base*layout(T).bytes)%16==0 &&
         reinterpret_cast<uintptr_t>(x+base)%16==0) {
        auto xv=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(x+base);
        for(unsigned j=0;j<8;++j)inputs[j]=xv[j];
        if constexpr(T==Type::F32) {
          auto w=reinterpret_cast<const sycl::vec<uint32_t,4>*>(row+base*4);
          auto lo=w[0],hi=w[1];
          for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
        } else {
          auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(row+base*2);
          for(unsigned j=0;j<8;++j) {
            if constexpr(T==Type::F16)values[j]=half(w[j]);
            else {auto bits=uint32_t(w[j])<<16;if((bits&0x7fffffff)>0x7f800000)bits|=0x400000;values[j]=bits_float(bits);}
          }
        }
      } else for(unsigned j=0;j<8 && base+j<k;++j){values[j]=element(T,row,base+j);inputs[j]=x[base+j];}
      for(unsigned j=0;j<8 && base+j<k;++j) {
        float input=a==Type::BF16?bits_float(uint32_t(inputs[j])<<16):half(inputs[j]);
        float product=values[j]*input;acc=acc+product;
      }
    }
    return acc;
  }
}
template<unsigned SG> float dispatch_dot(Type t,const uint8_t* row,const uint16_t* x,Type a,size_t k,unsigned lane) {
#define KOPT_CASE(T) case Type::T:return dot<Type::T,SG>(row,x,a,k,lane)
  switch(t) {
    KOPT_CASE(F32);KOPT_CASE(F16);KOPT_CASE(BF16);KOPT_CASE(Q8_0);KOPT_CASE(Q6_K);
    KOPT_CASE(Q3_K);KOPT_CASE(IQ3_XXS);KOPT_CASE(IQ2_S);KOPT_CASE(IQ3_S);KOPT_CASE(IQ4_NL);
  }
#undef KOPT_CASE
  return bits_float(0x7fc00000);
}
struct Multiply:ownrt::SyclOperation {
  std::array<Descriptor,4> desc{};unsigned matrices=0,subgroup=16;size_t groups=0,local_stride=16;
  template<unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto descriptions=desc;auto count=matrices;auto ng=groups,stride=local_stride;
    std::array<void*,28> pointers{};std::copy(p.begin(),p.end(),pointers.begin());
    return q.submit([&](sycl::handler& h) {
      h.depends_on(deps);sycl::local_accessor<uint8_t,1> storage(stride*rows_per_group,h);
      h.parallel_for(sycl::nd_range<1>(sycl::range<1>(ng*SG*rows_per_group),sycl::range<1>(SG*rows_per_group)),
        [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
          auto group=it.get_group_linear_id();auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
          unsigned row_in_group=sg.get_group_linear_id();
          unsigned which=0;for(unsigned j=1;j<count;++j)if(group>=descriptions[j].first_group)which=j;
          auto d=descriptions[which];size_t logical=(group-d.first_group)*rows_per_group+row_in_group;
          size_t slot=logical/d.span,row=logical%d.span;bool in_range=slot<d.count;
          Route r{0,0,uint32_t(d.rows)};
          if(d.routed && in_range)r=static_cast<const Route*>(pointers[d.r])[slot];
          bool valid=in_range && valid_route(r,d.experts,d.rows,d.span),active=valid && row<r.row_count;
          if(d.routed && in_range && row==0 && lane==0)static_cast<uint32_t*>(pointers[d.status])[slot]=valid?0:1;
          const uint8_t* source=nullptr;const uint16_t* x=nullptr;
          auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+row_in_group*stride;
          if(active) {
            source=static_cast<const uint8_t*>(pointers[d.w])+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb;
            x=static_cast<const uint16_t*>(pointers[d.x])+slot*d.k;
            if(layout(d.type).elements!=1)stage_row<SG>(source,local,d.rb,lane);
          }
          // All four rows reach the sole workgroup barrier, including invalid/tail rows.
          it.barrier(sycl::access::fence_space::local_space);
          float sum=0;
          if(active)sum=dispatch_dot<SG>(d.type,layout(d.type).elements==1?source:local,x,d.activation,d.k,lane);
          // Explicit adjacent-pair tree. Every lane participates in each shuffle;
          // only the left roots add. Never use implementation-chosen reduce().
          for(unsigned width=1;width<SG;width*=2) {
            float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);
            if(lane%(2*width)==0)sum=sum+rhs;
          }
          if(lane==0 && in_range) {
            float value=active?sum:bits_float(0x7fc00000);
            static_cast<uint16_t*>(pointers[d.y])[logical]=output_bits(value,d.output);
            if(d.diagnostic)static_cast<float*>(pointers[d.fp32])[logical]=value;
          }
        });
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    auto dev=q.get_device();auto supported=dev.get_info<sycl::info::device::sub_group_sizes>();
    auto local=dev.get_info<sycl::info::device::local_mem_size>();auto wg=dev.get_info<sycl::info::device::max_work_group_size>();
    if(std::find(supported.begin(),supported.end(),subgroup)==supported.end() || local_stride*rows_per_group>local || subgroup*rows_per_group>wg)
      throw std::invalid_argument("kopt unsupported device subgroup/SLM/workgroup");
    std::ostringstream info;info<<"{\"max_compute_units\":"<<dev.get_info<sycl::info::device::max_compute_units>()
      <<",\"local_mem_bytes\":"<<local<<",\"max_work_group_size\":"<<wg<<",\"subgroup_sizes\":[";
    for(size_t i=0;i<supported.size();++i)info<<(i?",":"")<<supported[i];
    properties=info.str()+"],\"occupancy\":\"not measured\"}";
    return subgroup==16?run<16>(q,p,deps):run<32>(q,p,deps);
  }
};
Descriptor bind_matrix(ownrt::Device& d,Multiply& op,std::vector<ownrt::Allocation>& ids,Matrix m,
                uint32_t experts,uint32_t count,uint32_t span,ownrt::Allocation r=0,ownrt::Allocation status=0) {
  geometry(m.type,m.activation,m.output_type,m.rows,m.columns,op.subgroup);
  if(!experts || !count || !span || span>m.rows)throw std::invalid_argument("kopt routes");
  auto l=layout(m.type);size_t rb=mul(m.columns/l.elements,l.bytes);
  Descriptor v{m.type,m.activation,m.output_type,m.rows,m.columns,rb,op.groups,(mul(count,span)+3)/4,experts,count,span,r!=0,0,0,0,0,0,0,m.fp32!=0};
  auto add=[&](ownrt::Allocation id,size_t bytes){check(d,id,bytes);unsigned index=ids.size();ids.push_back(id);return index;};
  v.w=add(m.w,mul(mul(experts,m.rows),rb));v.x=add(m.x,mul(mul(count,m.columns),2));v.y=add(m.y,mul(mul(count,span),2));
  if(r){v.r=add(r,mul(count,sizeof(Route)));v.status=add(status,mul(count,4));}
  if(m.fp32)v.fp32=add(m.fp32,mul(mul(count,span),4));
  if(l.elements!=1)op.local_stride=std::max(op.local_stride,(rb+15)/16*16);
  op.groups+=v.groups;return v;
}
ownrt::Event finish(ownrt::Device& d,Multiply& op,const std::vector<ownrt::Allocation>& ids) {
  if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
  mul(mul(op.groups,op.subgroup),rows_per_group);
  return d.compute(op,ids,{});
}
}
std::string device_properties(){return properties;}
ownrt::Event gemv(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,size_t rows,size_t k,Type a,Type o,unsigned sg,ownrt::Allocation fp32) {
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  op.desc[0]=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,fp32},1,1,rows);return finish(d,op,ids);
}
ownrt::Event routed_gemv(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,ownrt::Allocation r,ownrt::Allocation status,uint32_t experts,uint32_t rows,size_t k,uint32_t count,uint32_t span,Type a,Type o,unsigned sg,ownrt::Allocation fp32) {
  if(!r || !status)throw std::invalid_argument("kopt routing handles required");
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  op.desc[0]=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,fp32},experts,count,span,r,status);return finish(d,op,ids);
}
ownrt::Event fused_gemv(ownrt::Device& d,const std::vector<Matrix>& matrices,unsigned sg) {
  if(matrices.empty() || matrices.size()>4)throw std::invalid_argument("kopt fused matrix count1..4");
  Multiply op;op.subgroup=sg;op.matrices=matrices.size();std::vector<ownrt::Allocation> ids;
  for(size_t i=0;i<matrices.size();++i)op.desc[i]=bind_matrix(d,op,ids,matrices[i],1,1,matrices[i].rows);
  return finish(d,op,ids);
}
}
