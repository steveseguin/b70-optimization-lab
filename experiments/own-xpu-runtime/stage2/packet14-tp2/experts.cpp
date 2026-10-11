#include "tp.hpp"
#include "sycl_operation.hpp"
#include <array>
#include <algorithm>
namespace iq3::tp14 {
using namespace iq3::kopt4;
namespace {
void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes) {
 const auto& r=d.arena.row(id);
 if(!r.live || r.memory!=ownrt::Memory::device || !bytes || bytes>r.bytes || reinterpret_cast<uintptr_t>(r.pointer)%16)
  throw std::invalid_argument("device extent/alignment");
}
struct Share {
 sycl::sub_group sg;unsigned lane;
 template<class F> auto operator()(unsigned owner,F f)const {
  using R=decltype(f(owner));R v{};if(lane==owner)v=f(owner);return sycl::select_from_group(sg,v,owner);
 }
};
// Each descriptor has 7 bindings: packed,x,y,routes,status,optional-fp32,pad.
struct Projection:ownrt::SyclOperation {
 Type type,a,o;unsigned rows,k,experts,span,split,nmat,count;bool shared,diagnostic[2];
 template<Type T> sycl::event run(sycl::queue& q,std::span<void* const> ptr,const std::vector<sycl::event>& deps)const {
  std::array<void*,14> p{};std::copy(ptr.begin(),ptr.end(),p.begin());
  auto n=rows,cols=k,bank=experts,width=span,s=split,nm=nmat,slots=count;auto at=a,ot=o;auto shared_x=shared;
  std::array<bool,2> fp{diagnostic[0],diagnostic[1]};size_t rowgroups=(size_t(width)*s+3)/4;
  return q.submit([&](sycl::handler& h){
   h.depends_on(deps);sycl::local_accessor<float,1> partial(4,h);
   h.parallel_for(sycl::nd_range<3>({nm,slots,rowgroups*128},{1,1,128}),[=](sycl::nd_item<3> it) [[sycl::reqd_sub_group_size(32)]] {
    unsigned matrix=it.get_group(0),slot=it.get_group(1);auto sg=it.get_sub_group();
    unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id();
    unsigned row=it.get_group(2)*(4/s)+sub/s,part=sub%s;unsigned base=matrix*7;
    Route route=static_cast<const Route*>(p[base+3])[slot];
    bool valid=valid_route(route,bank,n,width),active=valid && row<route.row_count && row<width;
    if(it.get_group(2)==0 && it.get_local_linear_id()==0)static_cast<uint32_t*>(p[base+4])[slot]=valid?0:1;
    float sum=0;
    if(active) {
     constexpr auto l=layout(T);size_t rb=size_t(cols)/l.elements*l.bytes;
     auto w=static_cast<const uint8_t*>(p[base])+(size_t(route.expert_id)*n+route.row_begin+row)*rb;
     auto x=static_cast<const uint16_t*>(p[base+1])+(shared_x?0:size_t(slot)*cols);
     auto range=kopt2::bounds(cols,part,s);
     sum=kopt3::dot<T>(w,x,at,range.first,range.second,lane,kopt3::ConstantTables{},Share{sg,lane});
    }
    for(unsigned stride=1;stride<32;stride*=2){float other=sycl::select_from_group(sg,sum,(lane+stride)%32);if(lane%(stride*2)==0)sum=sum+other;}
    if(s==4) {
     if(lane==0)partial[sub]=sum;
     it.barrier(sycl::access::fence_space::local_space);
     if(sub==0 && lane==0) {float left=partial[0]+partial[1],right=partial[2]+partial[3];sum=left+right;}
    }
    if(lane==0 && part==0 && row<width) {
     float value=active?sum:bits_float(0x7fc00000);size_t offset=size_t(slot)*width+row;
     static_cast<uint16_t*>(p[base+2])[offset]=output_bits(value,ot);
     if(fp[matrix])static_cast<float*>(p[base+5])[offset]=value;
    }
   });
  });
 }
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const override {
  auto sizes=q.get_device().get_info<sycl::info::device::sub_group_sizes>();
  if(std::find(sizes.begin(),sizes.end(),32)==sizes.end() || q.get_device().get_info<sycl::info::device::max_work_group_size>()<128)throw std::invalid_argument("SG32/WG128 required");
#define CASE(T) case Type::T:return run<Type::T>(q,p,deps)
  switch(type){CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);default:break;}
#undef CASE
  throw std::invalid_argument("expert format");
 }
};
Launch project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared) {
 if((split!=1 && split!=4) || matrices.empty() || matrices.size()>2)throw std::invalid_argument("expert split/count");
 Projection op{};op.nmat=matrices.size();op.split=split;op.shared=shared;
 std::vector<ownrt::Allocation> ids;std::vector<std::pair<uint64_t,bool>> accesses;
 const auto& first=matrices.front();
 for(unsigned i=0;i<matrices.size();++i) {
  const auto& m=matrices[i];auto l=layout(m.type);unsigned span=m.span?m.span:m.rows;
  if((m.type!=Type::IQ2_S && m.type!=Type::IQ3_S && m.type!=Type::IQ4_NL) || !m.rows || m.rows>32768 || !m.columns || m.columns>17408 || m.columns%l.elements || !span || span>m.rows || !m.experts || m.experts>512 || (!m.count || m.count>10) || !m.routes || !m.status || (m.activation!=Type::BF16 && m.activation!=Type::F16) || (m.output_type!=Type::BF16 && m.output_type!=Type::F16))throw std::invalid_argument("expert geometry");
  if(i && (m.type!=first.type || m.rows!=first.rows || m.columns!=first.columns || m.span!=first.span || m.experts!=first.experts || m.activation!=first.activation || m.output_type!=first.output_type || m.x!=first.x || m.routes!=first.routes))throw std::invalid_argument("gate/up shared shape/input/routes");
  op.count=m.count;op.type=m.type;op.rows=m.rows;op.k=m.columns;op.experts=m.experts;op.span=span;op.a=m.activation;op.o=m.output_type;op.diagnostic[i]=m.fp32!=0;
  auto add=[&](ownrt::Allocation id,size_t bytes,bool write=false){check(device,id,bytes);ids.push_back(id);accesses.emplace_back(id,write);};
  add(m.w,size_t(m.experts)*m.rows*(m.columns/l.elements)*l.bytes);
  add(m.x,size_t(shared?1:m.count)*m.columns*2);add(m.y,size_t(m.count)*span*2,true);
  add(m.routes,m.count*sizeof(Route));add(m.status,m.count*4,true);
  if(m.fp32)add(m.fp32,size_t(m.count)*span*4,true);else ids.push_back(m.y);
  ids.push_back(m.x); // padding only; owner tracks every binding
 }
 kopt3::validate_aliases(accesses);
 auto e=device.compute(op,ids,{});return {e,e,1};
}
struct Combine:ownrt::SyclOperation {
 unsigned rows;bool diagnostic;
 sycl::event submit(sycl::queue& q,std::span<void* const> ptr,const std::vector<sycl::event>& deps)const override {
  auto y=static_cast<const uint16_t*>(ptr[0]);auto w=static_cast<const float*>(ptr[1]);auto out=static_cast<uint16_t*>(ptr[2]);auto fp=static_cast<float*>(ptr[3]);auto n=rows;auto diag=diagnostic;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((n+127)/128)*128,128),[=](sycl::nd_item<1> it){
   unsigned row=it.get_global_linear_id();if(row>=n)return;
   float sum=combine(y,w,n,row);out[row]=bf16_bits(sum);if(diag)fp[row]=sum;
  });});
 }
};
}
Launch expert_gate_up(ownrt::Device& d,const Matrix& gate,const Matrix& up,unsigned split){return project(d,{gate,up},split,true);}
Launch expert_down(ownrt::Device& d,const Matrix& down,unsigned split){return project(d,{down},split,false);}
Launch epilogue(ownrt::Device& d,ownrt::Allocation down,ownrt::Allocation weights,ownrt::Allocation out,unsigned rows,ownrt::Allocation fp) {
 if(!rows || rows>32768)throw std::invalid_argument("epilogue rows");
 check(d,down,size_t(10)*rows*2);check(d,weights,40);check(d,out,size_t(rows)*2);
 std::vector<std::pair<uint64_t,bool>> accesses{{down,false},{weights,false},{out,true}};
 if(fp){check(d,fp,size_t(rows)*4);accesses.emplace_back(fp,true);}
 kopt3::validate_aliases(accesses);Combine op;op.rows=rows;op.diagnostic=fp!=0;
 std::array ids{down,weights,out,fp?fp:out};auto e=d.compute(op,ids,{});return {e,e,1};
}
}
