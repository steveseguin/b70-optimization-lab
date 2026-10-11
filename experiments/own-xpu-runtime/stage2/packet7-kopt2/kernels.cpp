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
namespace iq3::kopt2 {
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
// Alignment is on each vector address, never a fictitious packed block boundary.
template<unsigned BYTES> inline void stage(const uint8_t* src,uint8_t* dst,size_t n,unsigned lane) {
  size_t prefix=stage_prefix(reinterpret_cast<uintptr_t>(src),n,BYTES);
  for(size_t i=lane;i<prefix;i+=32)dst[i]=src[i];
  size_t vectors=(n-prefix)/BYTES;
  if(vectors)assert(reinterpret_cast<uintptr_t>(src+prefix)%BYTES==0);
  auto p=reinterpret_cast<const sycl::vec<uint32_t,BYTES/4>*>(src+prefix);
  for(size_t v=lane;v<vectors;v+=32) {
    auto words=p[v];
    #pragma unroll
    for(unsigned j=0;j<BYTES/4;++j) {
      uint32_t word=words[j];
      #pragma unroll
      for(unsigned b=0;b<4;++b)dst[prefix+v*BYTES+j*4+b]=uint8_t(word>>(b*8));
    }
  }
  for(size_t i=prefix+vectors*BYTES+lane;i<n;i+=32)dst[i]=src[i];
}
// Raw inputs bypass SLM; vectorize contiguous groups without changing lane order.
inline float raw_lane(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t begin,size_t end,unsigned lane) {
  float acc=0;
  for(size_t k=begin+lane*8;k<end;k+=256) {
    float values[8];auto src=w+k*layout(t).bytes;
    if(k+8<=end && reinterpret_cast<uintptr_t>(src)%32==0 && t==Type::F32) {
      auto v=*reinterpret_cast<const sycl::vec<uint32_t,8>*>(src);
      #pragma unroll
      for(unsigned j=0;j<8;++j)values[j]=bits_float(v[j]);
    } else if(k+8<=end && reinterpret_cast<uintptr_t>(src)%16==0 && t!=Type::F32) {
      auto v=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(src);
      #pragma unroll
      for(unsigned j=0;j<8;++j) {
        if(t==Type::F16)values[j]=half(v[j]);
        else {uint32_t bits=uint32_t(v[j])<<16;if((bits&0x7fffffff)>0x7f800000)bits|=0x400000;values[j]=bits_float(bits);}
      }
    } else for(unsigned j=0;j<8 && k+j<end;++j)values[j]=element(t,w,k+j);
    #pragma unroll
    for(unsigned j=0;j<8;++j)if(k+j<end) {
      float input=a==Type::BF16?bits_float(uint32_t(x[k+j])<<16):half(x[k+j]);
      float product=values[j]*input;acc=acc+product;
    }
  }
  return acc;
}
struct Multiply:ownrt::SyclOperation {
  std::array<Desc,8> desc{};unsigned count=0,split=1,bytes=32;size_t groups=0,stride=64;bool reduce=false;
  template<unsigned BYTES> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto descriptors=desc;auto nm=count,ns=split;auto ng=groups,ld=stride;auto second=reduce;
    std::array<void*,64> ptr{};std::copy(p.begin(),p.end(),ptr.begin());
    // Wide: 4 subgroups x 2 rows. Split: 4 independent (row,split) subgroups.
    const unsigned rps=ns==1?2:1;
    return q.submit([&](sycl::handler& h){
      h.depends_on(deps);sycl::local_accessor<uint8_t,1> storage(ns==1?ld*8:1,h);
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
        size_t logical[2]{};bool active[2]{},in_range[2]{};const uint8_t* source[2]{};const uint16_t* x[2]{};
        unsigned part=ns==1?0:task%ns;
        #pragma unroll
        for(unsigned rr=0;rr<2;++rr)if(rr<rps) {
          logical[rr]=ns==1?task*2+rr:task/ns;
          size_t slot=logical[rr]/d.span,row=logical[rr]%d.span;
          in_range[rr]=slot<d.count;Route r{0,0,uint32_t(d.rows)};
          if(d.routed && in_range[rr])r=static_cast<const Route*>(ptr[d.r])[slot];
          bool valid=in_range[rr] && valid_route(r,d.experts,d.rows,d.span);active[rr]=valid && row<r.row_count;
          if(d.routed && in_range[rr] && row==0 && lane==0 && part==0)static_cast<uint32_t*>(ptr[d.status])[slot]=valid?0:1;
          if(active[rr]) {
            source[rr]=static_cast<const uint8_t*>(ptr[d.w])+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb;
            x[rr]=static_cast<const uint16_t*>(ptr[d.x])+slot*d.k;
            if(ns==1 && layout(d.type).elements!=1)stage<BYTES>(source[rr],storage.template get_multi_ptr<sycl::access::decorated::no>().get()+(sg.get_group_linear_id()*2+rr)*ld,d.rb,lane);
          }
        }
        if(ns==1)it.barrier(sycl::access::fence_space::local_space);
        #pragma unroll
        for(unsigned rr=0;rr<2;++rr)if(rr<rps) {
          float sum=0;auto range=bounds(d.k,part,ns);
          auto w=ns==1 && layout(d.type).elements!=1?storage.template get_multi_ptr<sycl::access::decorated::no>().get()+(sg.get_group_linear_id()*2+rr)*ld:source[rr];
          if(active[rr])sum=layout(d.type).elements==1?raw_lane(d.type,w,x[rr],d.a,range.first,range.second,lane):kopt2::lane(d.type,w,x[rr],d.a,range.first,range.second,lane);
          for(unsigned width=1;width<32;width*=2) {
            float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(width*2)==0)sum=sum+rhs;
          }
          if(lane==0 && in_range[rr]) {
            float value=active[rr]?sum:bits_float(0x7fc00000);
            if(ns>1)static_cast<float*>(ptr[d.ws])[logical[rr]*ns+part]=value;
            else {static_cast<uint16_t*>(ptr[d.y])[logical[rr]]=output_bits(value,d.o);if(d.diagnostic)static_cast<float*>(ptr[d.fp])[logical[rr]]=value;}
          }
        }
      });
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    capture(q);
    if((split==1?stride*8:1)>q.get_device().get_info<sycl::info::device::local_mem_size>() || q.get_device().get_info<sycl::info::device::max_work_group_size>()<128)
      throw std::invalid_argument("SLM/group device limit");
    return bytes==32?run<32>(q,p,deps):run<64>(q,p,deps);
  }
};
struct Stream:ownrt::SyclOperation {
  size_t bytes;bool copy=false;
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    capture(q);auto src=static_cast<const sycl::vec<uint32_t,4>*>(p[0]);auto dst=static_cast<uint64_t*>(p[1]);auto n=bytes;
    return q.submit([&](sycl::handler& h){h.depends_on(deps);
      if(copy){h.memcpy(dst,src,n);return;}
      h.parallel_for(sycl::nd_range<1>(stream_threads,128),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        auto lane=it.get_global_linear_id();uint64_t sum=0;
        for(size_t i=lane;i<n/16;i+=stream_threads) {
          auto v=src[i];
          #pragma unroll
          for(unsigned j=0;j<4;++j)sum+=v[j];
        }
        dst[lane]=sum;
      });
    });
  }
};
}
std::string device_properties(){return properties;}
size_t workspace_bytes(size_t rows,unsigned count,Variant v){return mul(mul(mul(rows,count),splits(v)),4);}
Launch multiply(ownrt::Device& device,const std::vector<Matrix>& matrices,Variant variant) {
  if(matrices.empty() || matrices.size()>8)throw std::invalid_argument("1..8 matrices");
  Multiply op;op.count=matrices.size();op.split=splits(variant);op.bytes=variant==Variant::wide64?64:32;
  std::vector<ownrt::Allocation> ids;
  for(unsigned i=0;i<matrices.size();++i) {
    auto m=matrices[i];auto l=layout(m.type);if(!m.span)m.span=m.rows;
    if(!l.elements || !m.rows || m.rows>UINT32_MAX || !m.columns || m.columns>17408 || m.columns%l.elements ||
      bool(m.routes)!=bool(m.status) || !m.experts || !m.count || !m.span || m.span>m.rows || (m.activation!=Type::BF16 && m.activation!=Type::F16) ||
      (m.output_type!=Type::BF16 && m.output_type!=Type::F16) || ((!m.routes || !m.status) && (m.experts!=1 || m.count!=1 || m.span!=m.rows)))
      throw std::invalid_argument("matrix geometry/type/routes");
    auto& d=op.desc[i];d={};d.type=m.type;d.a=m.activation;d.o=m.output_type;d.rows=m.rows;d.k=m.columns;d.rb=mul(m.columns/l.elements,l.bytes);
    d.first=op.groups;d.groups=(mul(mul(m.count,m.span),op.split)+(op.split==1?7:3))/(op.split==1?8:4);
    d.experts=m.experts;d.count=m.count;d.span=m.span;d.routed=m.routes!=0;d.diagnostic=m.fp32!=0;
    auto add=[&](ownrt::Allocation id,size_t n){check(device,id,n,id==m.w?64:16);unsigned index=ids.size();ids.push_back(id);return index;};
    d.w=add(m.w,mul(mul(m.experts,m.rows),d.rb));d.x=add(m.x,mul(mul(m.count,m.columns),2));d.y=add(m.y,mul(mul(m.count,m.span),2));
    if(d.routed){d.r=add(m.routes,mul(m.count,sizeof(Route)));d.status=add(m.status,mul(m.count,4));}
    if(d.diagnostic)d.fp=add(m.fp32,mul(mul(m.count,m.span),4));
    if(op.split>1)d.ws=add(m.workspace,workspace_bytes(m.span,m.count,variant));
    op.groups+=d.groups;if(l.elements!=1)op.stride=std::max(op.stride,(d.rb+63)/64*64);
  }
  if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("aliased bindings");
  auto first=device.compute(op,ids,{});if(op.split==1)return {first,first,1};
  op.reduce=true;op.groups=0;
  for(unsigned i=0;i<op.count;++i){auto& d=op.desc[i];d.first=op.groups;d.groups=(mul(d.count,d.span)+127)/128;op.groups+=d.groups;}
  std::array deps{first};auto last=device.compute(op,ids,deps);return {first,last,2};
}
ownrt::Event streaming_read(ownrt::Device& d,ownrt::Allocation src,ownrt::Allocation dst,size_t n) {
  if(n<64ull*1024*1024 || n>256ull*1024*1024 || n%16 || src==dst)throw std::invalid_argument("ceiling extent/alias");
  check(d,src,n);check(d,dst,stream_threads*8);Stream op;op.bytes=n;std::array ids{src,dst};return d.compute(op,ids,{});
}
ownrt::Event device_memcpy(ownrt::Device& d,ownrt::Allocation src,ownrt::Allocation dst,size_t n) {
  if(n<64ull*1024*1024 || n>256ull*1024*1024 || n%16 || src==dst)throw std::invalid_argument("ceiling extent/alias");
  check(d,src,n);check(d,dst,n);Stream op;op.bytes=n;op.copy=true;std::array ids{src,dst};return d.compute(op,ids,{});
}
}
