#include "kernels.hpp"
#include "sycl_operation.hpp"
#include <array>
#include <algorithm>
namespace iq3::kopt6 {
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
// Every bank is shuffled uniformly. Selecting a different bank in each source
// lane before the shuffle would return WRONG entries for divergent indices.
template<Type T> struct RegisterTables:kopt3::ConstantTables {
 sycl::sub_group sg;uint32_t low[T==Type::IQ2_S?32:16],high[T==Type::IQ2_S?32:1];
 explicit RegisterTables(sycl::sub_group group):sg(group) {
  unsigned lane=sg.get_local_linear_id();
  #pragma unroll
  for(unsigned bank=0;bank<(T==Type::IQ2_S?32:16);++bank) {
   if constexpr(T==Type::IQ2_S){auto v=iq2_s_grid[bank*32+lane];low[bank]=uint32_t(v);high[bank]=uint32_t(v>>32);}
   else low[bank]=iq3_s_grid[bank*32+lane];
  }
 }
 uint64_t iq2(unsigned i)const {
  uint32_t lo=0,hi=0;
  #pragma unroll
  for(unsigned b=0;b<32;++b) {
   auto l=sycl::select_from_group(sg,low[b],i%32),h=sycl::select_from_group(sg,high[b],i%32);
   if(i/32==b){lo=l;hi=h;}
  }
  return uint64_t(lo)|(uint64_t(hi)<<32);
 }
 uint32_t iq3s(unsigned i)const {
  uint32_t out=0;
  #pragma unroll
  for(unsigned b=0;b<16;++b){auto v=sycl::select_from_group(sg,low[b],i%32);if(i/32==b)out=v;}
  return out;
 }
};
struct SlmTables:kopt3::ConstantTables {
 const uint32_t* data;
 explicit SlmTables(const uint32_t* p):data(p){}
 uint64_t iq2(unsigned i)const{return uint64_t(data[2*i])|(uint64_t(data[2*i+1])<<32);}
 uint32_t iq3s(unsigned i)const{return data[i];}
};
// Each descriptor has 7 bindings: packed,x,y,routes,status,optional-fp32,pad.
struct Projection:ownrt::SyclOperation {
 Type type,a,o;unsigned rows,k,experts,span,split,nmat;bool shared,diagnostic[2];Variant variant;
 template<Type T,Variant V> sycl::event run(sycl::queue& q,std::span<void* const> ptr,const std::vector<sycl::event>& deps)const {
  std::array<void*,14> p{};std::copy(ptr.begin(),ptr.end(),p.begin());
  auto n=rows,cols=k,bank=experts,width=span,s=split,nm=nmat;auto at=a,ot=o;auto shared_x=shared;
  std::array<bool,2> fp{diagnostic[0],diagnostic[1]};size_t rowgroups=(size_t(width)*s+3)/4;
  return q.submit([&](sycl::handler& h){
   h.depends_on(deps);sycl::local_accessor<float,1> partial(4,h);
   constexpr bool slm=V==Variant::slm_pair && T!=Type::IQ4_NL;
   sycl::local_accessor<uint32_t,1> grid(slm?(T==Type::IQ2_S?2048:512):1,h);
   h.parallel_for(sycl::nd_range<3>({nm,10,rowgroups*128},{1,1,128}),[=](sycl::nd_item<3> it) [[sycl::reqd_sub_group_size(32)]] {
    if constexpr(slm) {
     unsigned wi=it.get_local_linear_id();
     if constexpr(T==Type::IQ2_S)for(unsigned i=wi;i<1024;i+=128){auto v=iq2_s_grid[i];grid[2*i]=uint32_t(v);grid[2*i+1]=uint32_t(v>>32);}
     else for(unsigned i=wi;i<512;i+=128)grid[i]=iq3_s_grid[i];
     it.barrier(sycl::access::fence_space::local_space);
    }
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
     if constexpr(V==Variant::registers && T!=Type::IQ4_NL) {
      RegisterTables<T> tables(sg);
      sum=dot<T,V,sycl::float8>(w,x,at,range.first,range.second,lane,tables,Share{sg,lane});
     } else if constexpr(slm) {
      SlmTables tables(grid.template get_multi_ptr<sycl::access::decorated::no>().get());
      sum=dot<T,V,sycl::float8>(w,x,at,range.first,range.second,lane,tables,Share{sg,lane});
     } else sum=dot<T,V,sycl::float8>(w,x,at,range.first,range.second,lane,kopt3::ConstantTables{},Share{sg,lane});
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
#define CASE(T) case Type::T:switch(variant){case Variant::baseline:return run<Type::T,Variant::baseline>(q,p,deps);case Variant::registers:return run<Type::T,Variant::registers>(q,p,deps);case Variant::slm_pair:return run<Type::T,Variant::slm_pair>(q,p,deps);case Variant::packed_pipeline:return run<Type::T,Variant::packed_pipeline>(q,p,deps);}break
  switch(type){CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);default:break;}
#undef CASE
  throw std::invalid_argument("expert format");
 }
};
Launch project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared,Variant variant) {
 if((split!=1 && split!=4) || matrices.empty() || matrices.size()>2)throw std::invalid_argument("expert split/count");
 Projection op{};op.variant=variant;op.nmat=matrices.size();op.split=split;op.shared=shared;
 std::vector<ownrt::Allocation> ids;std::vector<std::pair<uint64_t,bool>> accesses;
 const auto& first=matrices.front();
 for(unsigned i=0;i<matrices.size();++i) {
  const auto& m=matrices[i];auto l=layout(m.type);unsigned span=m.span?m.span:m.rows;
  if((m.type!=Type::IQ2_S && m.type!=Type::IQ3_S && m.type!=Type::IQ4_NL) || !m.rows || m.rows>32768 || !m.columns || m.columns>17408 || m.columns%l.elements || !span || span>m.rows || !m.experts || m.experts>512 || m.count!=10 || !m.routes || !m.status || (m.activation!=Type::BF16 && m.activation!=Type::F16) || (m.output_type!=Type::BF16 && m.output_type!=Type::F16))throw std::invalid_argument("expert geometry");
  if(i && (m.type!=first.type || m.rows!=first.rows || m.columns!=first.columns || m.span!=first.span || m.experts!=first.experts || m.activation!=first.activation || m.output_type!=first.output_type || m.x!=first.x || m.routes!=first.routes))throw std::invalid_argument("gate/up shared shape/input/routes");
  op.type=m.type;op.rows=m.rows;op.k=m.columns;op.experts=m.experts;op.span=span;op.a=m.activation;op.o=m.output_type;op.diagnostic[i]=m.fp32!=0;
  auto add=[&](ownrt::Allocation id,size_t bytes,bool write=false){check(device,id,bytes);ids.push_back(id);accesses.emplace_back(id,write);};
  add(m.w,size_t(m.experts)*m.rows*(m.columns/l.elements)*l.bytes);
  add(m.x,size_t(shared?1:10)*m.columns*2);add(m.y,size_t(10)*span*2,true);
  add(m.routes,10*sizeof(Route));add(m.status,40,true);
  if(m.fp32)add(m.fp32,size_t(10)*span*4,true);else ids.push_back(m.y);
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
Launch expert_gate_up(ownrt::Device& d,const Matrix& gate,const Matrix& up,unsigned split,Variant v){return project(d,{gate,up},split,true,v);}
Launch expert_down(ownrt::Device& d,const Matrix& down,unsigned split,Variant v){return project(d,{down},split,false,v);}
Launch epilogue(ownrt::Device& d,ownrt::Allocation down,ownrt::Allocation weights,ownrt::Allocation out,unsigned rows,ownrt::Allocation fp) {
 if(!rows || rows>32768)throw std::invalid_argument("epilogue rows");
 check(d,down,size_t(10)*rows*2);check(d,weights,40);check(d,out,size_t(rows)*2);
 std::vector<std::pair<uint64_t,bool>> accesses{{down,false},{weights,false},{out,true}};
 if(fp){check(d,fp,size_t(rows)*4);accesses.emplace_back(fp,true);}
 kopt3::validate_aliases(accesses);Combine op;op.rows=rows;op.diagnostic=fp!=0;
 std::array ids{down,weights,out,fp?fp:out};auto e=d.compute(op,ids,{});return {e,e,1};
}
Launch multiply_dispatched(ownrt::Device& d,const Matrix& m) {
 if(m.routes || m.experts!=1 || m.count!=1)throw std::invalid_argument("dense dispatch cannot accept routed matrices");
 unsigned v=dispatch_variant(unsigned(m.type),m.rows,m.columns,m.experts);
 if(v==0){auto e=kopt::gemv(d,m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,32,m.fp32);return {e,e,1};}
 if(v==1){auto l=kopt2::multiply(d,{m},kopt2::Variant::split4);return {l.first,l.last,l.passes};}
 return kopt3::multiply(d,{m},v==2?kopt3::Variant::constant:v==3?kopt3::Variant::slm:v==4?kopt3::Variant::constant_split4:kopt3::Variant::slm_split4);
}
}
