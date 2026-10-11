#include "kernels.hpp"
#include "sycl_operation.hpp"
#include <array>
namespace iq3::expanded {
namespace {
struct Decode:ownrt::SyclOperation {
 Type type;unsigned rows,k;size_t rb;
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const override {
  auto w=static_cast<const uint8_t*>(p[0]);auto out=static_cast<float*>(p[1]);auto t=type;auto n=rows,cols=k;auto stride=rb;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(size_t(n)*cols),[=](sycl::id<1> id){size_t i=id[0];out[i]=value(t,w+(i/cols)*stride,cols,i%cols);});});
 }
};
struct Multiply:ownrt::SyclOperation {
 Type t,a,o;size_t rows,k,rb;unsigned split;bool diagnostic;
 template<Type T> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const {
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto fp=static_cast<float*>(p[3]);
  auto n=rows,cols=k,stride=rb;auto s=split;auto at=a,ot=o;auto diag=diagnostic;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> partial(4,h);
   h.parallel_for(sycl::nd_range<1>(((n*s+3)/4)*128,128),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
    auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id(),sub=sg.get_group_linear_id();size_t r=it.get_group_linear_id()*(4/s)+sub/s;unsigned part=sub%s;
    float sum=0;
    if(r<n){auto bounds=kopt2::bounds(cols,part,s);sum=lane(T,w+r*stride,x,at,cols,bounds.first,bounds.second,l);}
    for(unsigned width=1;width<32;width*=2){float other=sycl::select_from_group(sg,sum,(l+width)%32);if(l%(2*width)==0)sum=sum+other;}
    if(s==4){if(l==0)partial[sub]=sum;it.barrier(sycl::access::fence_space::local_space);if(sub==0 && l==0)sum=(partial[0]+partial[1])+(partial[2]+partial[3]);}
    if(r<n && l==0 && part==0){y[r]=output_bits(sum,ot);if(diag)fp[r]=sum;}
   });
  });
 }
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const override {
  auto sizes=q.get_device().get_info<sycl::info::device::sub_group_sizes>();
  if(std::find(sizes.begin(),sizes.end(),32)==sizes.end() || q.get_device().get_info<sycl::info::device::max_work_group_size>()<128)throw std::invalid_argument("SG32/WG128 required");
#define CASE(T) case Type::T:return run<Type::T>(q,p,deps)
  switch(t){CASE(F32);CASE(F16);CASE(BF16);CASE(Q8_0);CASE(Q3_K);CASE(Q6_K);CASE(IQ3_XXS);CASE(IQ4_NL);CASE(IQ3_S);CASE(IQ2_S);default:if(t==IQ4_XS)return run<IQ4_XS>(q,p,deps);}
#undef CASE
  throw std::invalid_argument("expanded type");
 }
};
}
ownrt::Event dequant(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation y,unsigned rows,unsigned k){
 if(!rows || rows>248320 || w==y)throw std::invalid_argument("decode rows/alias");auto rb=row_bytes(t,k);
 for(auto [id,bytes]:{std::pair{w,size_t(rows)*rb},std::pair{y,size_t(rows)*k*4}}){auto r=d.arena.row(id);if(!r.live || r.memory!=ownrt::Memory::device || bytes>r.bytes)throw std::invalid_argument("decode extent");}
 Decode op;op.type=t;op.rows=rows;op.k=k;op.rb=rb;std::array ids{w,y};return d.compute(op,ids,{});
}
kopt3::Launch gemv(ownrt::Device& d,const kopt3::Matrix& m,unsigned split){
 if((split!=1 && split!=4) || !m.rows || m.rows>248320 || m.experts!=1 || m.count!=1 || m.routes || m.status || (m.span && m.span!=m.rows) || (m.activation!=Type::F16 && m.activation!=Type::BF16) || (m.output_type!=Type::F16 && m.output_type!=Type::BF16))throw std::invalid_argument("expanded dense geometry");
 size_t rb=row_bytes(m.type,m.columns);std::vector<ownrt::Allocation> ids;std::vector<std::pair<uint64_t,bool>> accesses;
 auto add=[&](ownrt::Allocation id,size_t bytes,bool write){auto r=d.arena.row(id);if(!r.live || r.memory!=ownrt::Memory::device || bytes>r.bytes || reinterpret_cast<uintptr_t>(r.pointer)%16)throw std::invalid_argument("expanded extent/alignment");ids.push_back(id);accesses.emplace_back(id,write);};
 add(m.w,m.rows*rb,false);add(m.x,m.columns*2,false);add(m.y,m.rows*2,true);if(m.fp32)add(m.fp32,m.rows*4,true);else ids.push_back(m.y);
 kopt3::validate_aliases(accesses);Multiply op;op.t=m.type;op.a=m.activation;op.o=m.output_type;op.rows=m.rows;op.k=m.columns;op.rb=rb;op.split=split;op.diagnostic=m.fp32!=0;
 auto e=d.compute(op,ids,{});return {e,e,1};
}
}
