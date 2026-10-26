#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet6-kopt/kernels.hpp"
#include "stage2/packet6-kopt/reference.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_switches.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_reuse2_op.hpp"
#include "stage2/packet194-expert-diet-engine/detmath.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include "stage2/packet6-kopt/dense_v2.hpp"
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
     (!(a==Type::F32 && o==Type::F32) && ((a!=Type::BF16 && a!=Type::F16) || (o!=Type::BF16 && o!=Type::F16))) || (sg!=16 && sg!=32))
    throw std::invalid_argument("kopt geometry/type/subgroup");
}
struct Descriptor {
  Type type,activation,output;size_t rows,k,rb,first_group,groups;
  uint32_t experts,count,span;bool routed;
  unsigned w,x,y,r,status,fp32;bool diagnostic;
  // Dense token rows (gemv_tokens): slots are tokens, ordered row-major so tokens sharing a weight row run together.
  bool row_major=false;
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
    // F32 activations with 16-byte aligned row and input: every full chunk below takes the vector branch (its
    // alignment test is the same for all chunks), so run those chunks as a fixed-trip unrolled body with a 32-bit
    // index, then the ragged chunk exactly as below. Same values, same order.
    if(a==Type::F32 && reinterpret_cast<uintptr_t>(row)%16==0 && reinterpret_cast<uintptr_t>(x)%16==0) {
      const float* xf=reinterpret_cast<const float*>(x);const uint32_t k32=uint32_t(k);uint32_t base=lane*8u;
      #pragma unroll 2
      for(;base+8u<=k32;base+=SG*8u) {
        float values[8],wide[8];
        #pragma unroll
        for(unsigned j=0;j<8;++j)wide[j]=xf[base+j];
        if constexpr(T==Type::F32) {
          auto w=reinterpret_cast<const sycl::vec<uint32_t,4>*>(row+size_t(base)*4);
          auto lo=w[0],hi=w[1];
          #pragma unroll
          for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
        } else {
          auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(row+size_t(base)*2);
          #pragma unroll
          for(unsigned j=0;j<8;++j) {
            // BF16: no explicit NaN-quieting here. Finite weights are bit-identical; a NaN weight's product below is the
            // same quiet NaN either way (the multiply quiets it). HC low+inject microbench, cold: 24.9 -> 23.1 us.
            if constexpr(T==Type::F16)values[j]=half(w[j]);
            else values[j]=bits_float(uint32_t(w[j])<<16);
          }
        }
        #pragma unroll
        for(unsigned j=0;j<8;++j){float product=values[j]*wide[j];acc=acc+product;}
      }
      if(base<k32) {
        float values[8],wide[8];
        for(unsigned j=0;base+j<k32;++j){values[j]=element(T,row,base+j);wide[j]=xf[base+j];}
        for(unsigned j=0;base+j<k32;++j){float product=values[j]*wide[j];acc=acc+product;}
      }
      return acc;
    }
    for(size_t base=size_t(lane)*8;base<k;base+=SG*8) {
      float values[8];uint16_t inputs[8];float wide[8];const bool f32=a==Type::F32;
      if(base+8<=k && reinterpret_cast<uintptr_t>(row+base*layout(T).bytes)%16==0 &&
         reinterpret_cast<uintptr_t>(x+base)%16==0) {
        if(f32){for(unsigned j=0;j<8;++j)wide[j]=reinterpret_cast<const float*>(x)[base+j];}
        else{auto xv=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(x+base);
        for(unsigned j=0;j<8;++j)inputs[j]=xv[j];}
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
      } else for(unsigned j=0;j<8 && base+j<k;++j){values[j]=element(T,row,base+j);if(f32)wide[j]=reinterpret_cast<const float*>(x)[base+j];else inputs[j]=x[base+j];}
      for(unsigned j=0;j<8 && base+j<k;++j) {
        float input=f32?wide[j]:a==Type::BF16?bits_float(uint32_t(inputs[j])<<16):half(inputs[j]);
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
// OWNRT_DENSE_DECODE_V2=1 (lab 2026-10-26, default off): dense quantized decode rows with Multiply's own row staging
// (stage_row into local memory) and per-lane dot (dot<T,SG>, i.e. lane_dot on the staged copy), R rows per subgroup in
// the subgroup's own local region (a subgroup barrier instead of the work-group barrier), subgroup-uniform row index,
// and the R adjacent-pair trees reduced together by a transposing butterfly (node = lower lane block + upper lane
// block). Every output is Multiply's value.
template<Type T,unsigned R> inline void quant_rows_staged(const std::array<dense_v2::Mat,4>& m,unsigned count,size_t stride,uint8_t* slm,sycl::nd_item<1> it){
  constexpr unsigned LR=R==1?0:R==2?1:R==4?2:3;
  auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id();
  const uint32_t gsub=uint32_t(it.get_group_linear_id())*uint32_t(it.get_local_range(0)/32)+uint32_t(sub);unsigned j=0;
  for(unsigned t=1;t<count;++t)if(gsub>=m[t].first_sub)j=t;
  const dense_v2::Mat d=m[j];const uint32_t row0=(gsub-d.first_sub)*R;if(row0>=d.rows)return;
  uint8_t* local=slm+size_t(sub)*R*stride;
  #pragma unroll
  for(unsigned r=0;r<R;++r){const uint32_t row=row0+r<d.rows?row0+r:row0;stage_row<32>(d.w+size_t(row)*d.rb,local+r*stride,d.rb,lane);}
  sycl::group_barrier(sg);
  float A[R];
  #pragma unroll
  for(unsigned r=0;r<R;++r)A[r]=dot<T,32>(local+r*stride,reinterpret_cast<const uint16_t*>(d.x),Type::F32,d.k,lane);
  #pragma unroll
  for(unsigned lv=0;lv<LR;++lv){const bool hi=((lane>>lv)&1u)!=0;
    #pragma unroll
    for(unsigned q=0;q<(R>>(lv+1));++q){const float lo_v=A[2*q],hi_v=A[2*q+1];const float send=hi?lo_v:hi_v,mine=hi?hi_v:lo_v;
      const float recv=sycl::permute_group_by_xor(sg,send,1u<<lv);A[q]=hi?recv+mine:mine+recv;}}
  #pragma unroll
  for(unsigned lv=LR;lv<5;++lv){const float o=sycl::permute_group_by_xor(sg,A[0],1u<<lv);A[0]=((lane>>lv)&1u)?o+A[0]:A[0]+o;}
  const uint32_t row=row0+(lane&(R-1));
  if(lane<R&&row<d.rows)d.y[row]=A[0];
}
struct Multiply:ownrt::SyclOperation {
  std::array<Descriptor,4> desc{};unsigned matrices=0,subgroup=16;size_t groups=0,local_stride=16;
  template<Type T,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    // Several independent matrices of one type share a launch (sibling fusion): work-groups are partitioned by each
    // descriptor's first_group, and every row runs the unchanged single-matrix code with its own descriptor.
    if(matrices<1||matrices>desc.size())throw std::invalid_argument("kopt matrix count");
    for(unsigned j=1;j<matrices;++j)if(desc[j].type!=desc[0].type||desc[j].activation!=desc[0].activation||desc[j].output!=desc[0].output||desc[j].routed)throw std::invalid_argument("kopt fused matrices must share type/activation/output and be dense");
    auto descriptors=desc;const unsigned count=matrices;auto ng=groups,stride=local_stride;
    std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("packet26 capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    if constexpr(layout(T).elements!=1&&SG==32)if(dense_v2::enabled()){
      // Dense quantized rows (R per subgroup, quant_rows_staged). Anything else keeps this kernel.
      std::array<dense_v2::Mat,4> m{};bool ok=true;uint32_t maxk=0;size_t maxrb=0;
      for(unsigned j=0;j<count;++j){const auto& d=descriptors[j];
        ok=ok&&!d.routed&&!d.diagnostic&&!d.row_major&&d.count==1&&d.experts==1&&d.span==d.rows&&d.activation==Type::F32&&d.output==Type::F32&&d.rows<=UINT32_MAX&&d.k<=16384;
        maxk=std::max(maxk,uint32_t(d.k));maxrb=std::max(maxrb,d.rb);}
      const size_t qstride=(maxrb+15)/16*16;
      if(ok&&qstride==stride&&stride*(maxk<=1024?4:2)*4<=65536){const unsigned R=maxk<=1024?4:2;uint32_t subs=0;
        for(unsigned j=0;j<count;++j){const auto& d=descriptors[j];m[j]=dense_v2::Mat{static_cast<const uint8_t*>(pointers[d.w]),static_cast<const float*>(pointers[d.x]),static_cast<float*>(pointers[d.y]),uint32_t(d.rows),uint32_t(d.k),uint32_t(d.rb),subs};subs+=(uint32_t(d.rows)+R-1)/R;}
        const size_t global=(size_t(subs)*32+127)/128*128;
        if(R==4)return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(global),sycl::range<1>(128))](sycl::handler& h){
          sycl::local_accessor<uint8_t,1> storage(stride*4*4,h);
          h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{quant_rows_staged<T,4>(m,count,stride,storage.template get_multi_ptr<sycl::access::decorated::no>().get(),it);}));});
        return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(global),sycl::range<1>(128))](sycl::handler& h){
          sycl::local_accessor<uint8_t,1> storage(stride*2*4,h);
          h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{quant_rows_staged<T,2>(m,count,stride,storage.template get_multi_ptr<sycl::access::decorated::no>().get(),it);}));});
      }
    }
    if constexpr(T==Type::BF16&&SG==32)if(dense_v2::enabled()){
      // OWNRT_DENSE_DECODE_V2=1 (lab 2026-10-26, default off): dense BF16 rows, F32 in/out, R rows per subgroup with the
      // same per-row lane chunks, order and tree (dense_v2.hpp). Anything else keeps this kernel.
      std::array<dense_v2::Mat,4> m{};bool ok=true;uint32_t subs=0,maxrows=0,maxk=0;
      for(unsigned j=0;j<count;++j){const auto& d=descriptors[j];
        ok=ok&&!d.routed&&!d.diagnostic&&!d.row_major&&d.count==1&&d.experts==1&&d.span==d.rows&&d.activation==Type::F32&&d.output==Type::F32&&
          d.rb==d.k*2&&d.rb%16==0&&d.rows<=UINT32_MAX&&d.k<=16384&&reinterpret_cast<uintptr_t>(pointers[d.w])%16==0&&reinterpret_cast<uintptr_t>(pointers[d.x])%16==0;
        maxrows=std::max(maxrows,uint32_t(d.rows));maxk=std::max(maxk,uint32_t(d.k));}
      if(ok){const bool small_k=maxk<=1024&&maxrows>=2048;const uint32_t R=small_k?4:1;
        for(unsigned j=0;j<count;++j){const auto& d=descriptors[j];m[j]=dense_v2::Mat{static_cast<const uint8_t*>(pointers[d.w]),static_cast<const float*>(pointers[d.x]),static_cast<float*>(pointers[d.y]),uint32_t(d.rows),uint32_t(d.k),uint32_t(d.rb),subs};subs+=(uint32_t(d.rows)+R-1)/R;}
        const size_t global=(size_t(subs)*32+127)/128*128;
        if(small_k)return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(global),sycl::range<1>(128))](sycl::handler& h){
          h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{dense_v2::bf16_multi<4,4>(m,count,it);}));});
        return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(global),sycl::range<1>(128))](sycl::handler& h){
          h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{dense_v2::bf16_multi<1,8>(m,count,it);}));});
      }
    }
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(ng*SG*rows_per_group),sycl::range<1>(SG*rows_per_group))](sycl::handler& h) {
      sycl::local_accessor<uint8_t,1> storage(stride*rows_per_group,h);
      h.parallel_for(p35_range0,
        packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
          auto group=it.get_group_linear_id();auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
          unsigned row_in_group=sg.get_group_linear_id();
          auto d=descriptors[0];for(unsigned j=1;j<count;++j)if(group>=descriptors[j].first_group)d=descriptors[j];
          size_t logical=(group-d.first_group)*rows_per_group+row_in_group;
          size_t slot=d.row_major?logical%d.count:logical/d.span,row=d.row_major?logical/d.count:logical%d.span;bool in_range=d.row_major?row<d.span:slot<d.count;
          Route r{0,0,uint32_t(d.rows)};
          if(d.routed && in_range)r=static_cast<const Route*>(pointers[d.r])[slot];
          bool valid=in_range && valid_route(r,d.experts,d.rows,d.span),active=valid && row<r.row_count;
          if(d.routed && in_range && row==0 && lane==0)static_cast<uint32_t*>(pointers[d.status])[slot]=valid?0:1;
          const uint8_t* source=nullptr;const uint16_t* x=nullptr;
          auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+row_in_group*stride;
          if(active) {
            source=static_cast<const uint8_t*>(pointers[d.w])+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb;
            x=d.activation==Type::F32?reinterpret_cast<const uint16_t*>(static_cast<const float*>(pointers[d.x])+slot*d.k):static_cast<const uint16_t*>(pointers[d.x])+slot*d.k;
            if(layout(T).elements!=1)stage_row<SG>(source,local,d.rb,lane);
          }
          // All four rows reach the sole workgroup barrier, including invalid/tail rows.
          it.barrier(sycl::access::fence_space::local_space);
          float sum=0;
          if(active)sum=dot<T,SG>(layout(T).elements==1?source:local,x,d.activation,d.k,lane);
          // Explicit adjacent-pair tree. Every lane participates in each shuffle;
          // only the left roots add. Never use implementation-chosen reduce().
          for(unsigned width=1;width<SG;width*=2) {
            float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);
            if(lane%(2*width)==0)sum=sum+rhs;
          }
          if(lane==0 && in_range) {
            float value=active?sum:bits_float(0x7fc00000);
            const size_t out=slot*d.span+row; // == logical for the slot-major mapping
            if(d.output==Type::F32)static_cast<float*>(pointers[d.y])[out]=value;else static_cast<uint16_t*>(pointers[d.y])[out]=output_bits(value,d.output);
            if(d.diagnostic)static_cast<float*>(pointers[d.fp32])[out]=value;
          }
        }));
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
    switch(desc[0].type){
#define P26_CASE(T) case Type::T:return subgroup==16?run<Type::T,16>(q,p,deps):run<Type::T,32>(q,p,deps)
P26_CASE(F32);P26_CASE(F16);P26_CASE(BF16);P26_CASE(Q8_0);P26_CASE(Q6_K);P26_CASE(Q3_K);P26_CASE(IQ3_XXS);P26_CASE(IQ2_S);P26_CASE(IQ3_S);P26_CASE(IQ4_NL);
#undef P26_CASE
}throw std::invalid_argument("type");
  }
};
// Dense token rows with weight reuse: one subgroup owns one weight row and a tile of R token rows. Each weight value
// is decoded once and applied to every token of the tile; each token keeps Multiply's single-row arithmetic exactly
// (lane k-ranges, decode, product then add, the adjacent-pair subgroup tree). F32 activations only.
template<unsigned R> struct MultiplyRows:ownrt::SyclOperation {
  Descriptor desc{};unsigned subgroup=16;size_t groups=0,local_stride=16;
  template<Type T,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;auto ng=groups,stride=local_stride;
    std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt rows capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(ng*SG*rows_per_group),sycl::range<1>(SG*rows_per_group))](sycl::handler& h) {
      sycl::local_accessor<uint8_t,1> storage(stride*rows_per_group,h);
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();unsigned row_in_group=sg.get_group_linear_id();
        const size_t tiles=(d.count+R-1)/R,logical=it.get_group_linear_id()*rows_per_group+row_in_group;
        const size_t row=logical/tiles,first=(logical%tiles)*R;const bool active=row<d.span;
        const unsigned n=active?unsigned(std::min<size_t>(R,d.count-first)):0;
        const uint8_t* source=nullptr;auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+row_in_group*stride;
        if(active){source=static_cast<const uint8_t*>(pointers[d.w])+row*d.rb;if(layout(T).elements!=1)stage_row<SG>(source,local,d.rb,lane);}
        it.barrier(sycl::access::fence_space::local_space);
        const float* x=static_cast<const float*>(pointers[d.x])+first*d.k;
        float acc[R];for(unsigned r=0;r<R;++r)acc[r]=0;
        if(active) {
          if constexpr(layout(T).elements==1) {
            for(size_t base=size_t(lane)*8;base<d.k;base+=SG*8) {
              float values[8];
              if(base+8<=d.k && reinterpret_cast<uintptr_t>(source+base*layout(T).bytes)%16==0) {
                if constexpr(T==Type::F32) {
                  auto w=reinterpret_cast<const sycl::vec<uint32_t,4>*>(source+base*4);auto lo=w[0],hi=w[1];
                  for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
                } else {
                  auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(source+base*2);
                  for(unsigned j=0;j<8;++j) {
                    if constexpr(T==Type::F16)values[j]=half(w[j]);
                    else {auto bits=uint32_t(w[j])<<16;if((bits&0x7fffffff)>0x7f800000)bits|=0x400000;values[j]=bits_float(bits);}
                  }
                }
              } else for(unsigned j=0;j<8 && base+j<d.k;++j)values[j]=element(T,source,base+j);
              for(unsigned r=0;r<R;++r)if(r<n)for(unsigned j=0;j<8 && base+j<d.k;++j){float input=x[r*d.k+base+j];float product=values[j]*input;acc[r]=acc[r]+product;}
            }
          } else {
            for(size_t k=size_t(lane)*8;k<d.k;k+=size_t(SG)*8) {
              float values[8];
              if(k+8<=d.k)decode8<T>(local,k,values);else for(size_t j=0;j<d.k-k;++j)values[j]=element(T,local,k+j);
              for(unsigned r=0;r<R;++r)if(r<n)for(unsigned j=0;j<8 && k+j<d.k;++j){float input=x[r*d.k+k+j];float product=values[j]*input;acc[r]=acc[r]+product;}
            }
          }
        }
        for(unsigned r=0;r<R;++r){float sum=acc[r];
          for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
          if(lane==0&&r<n)static_cast<float*>(pointers[d.y])[(first+r)*d.span+row]=sum;}
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){
#define ROWS_CASE(T) case Type::T:return subgroup==16?run<Type::T,16>(q,p,deps):run<Type::T,32>(q,p,deps)
ROWS_CASE(F32);ROWS_CASE(F16);ROWS_CASE(BF16);ROWS_CASE(Q8_0);ROWS_CASE(Q6_K);
#undef ROWS_CASE
    default:break;}
    throw std::invalid_argument("kopt token rows: dense F32/F16/BF16/Q8_0/Q6_K only");
  }
};
// Dense token rows, tiled: a work-group of 4 subgroups owns 4*RowsPerSubgroup weight rows and up to Tokens token rows.
// Each 256-column slice of the tokens' F32 activations is staged once in local memory (transposed, so the 32 lanes of a
// subgroup read 32 consecutive floats) and reused by all the work-group's weight rows; each weight value is decoded
// once and applied to every token. Tokens beyond the chunk read zeros and are never written. Every real output (row,
// token) keeps Multiply's single-row arithmetic exactly: lane l owns columns l*8+256*i+j (SG=32), product then add in
// that order, then the adjacent-pair subgroup tree.
template<unsigned RowsPerSubgroup,unsigned Tokens> struct MultiplyTiled:ownrt::SyclOperation {
  static constexpr unsigned SG=32,Subgroups=4,Rows=RowsPerSubgroup*Subgroups,Step=SG*8;
  Descriptor desc{};
  template<Type T> static inline void values8(const uint8_t* source,size_t base,size_t k,float* values) {
    if constexpr(layout(T).elements==1) {
      if(base+8<=k && reinterpret_cast<uintptr_t>(source+base*layout(T).bytes)%16==0) {
        if constexpr(T==Type::F32) {
          auto v=reinterpret_cast<const sycl::vec<uint32_t,4>*>(source+base*4);auto lo=v[0],hi=v[1];
          for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
        } else {
          auto v=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(source+base*2);
          for(unsigned j=0;j<8;++j) {
            if constexpr(T==Type::F16)values[j]=half(v[j]);
            else {auto bits=uint32_t(v[j])<<16;if((bits&0x7fffffff)>0x7f800000)bits|=0x400000;values[j]=bits_float(bits);}
          }
        }
      } else for(unsigned j=0;j<8 && base+j<k;++j)values[j]=element(T,source,base+j);
    } else {
      if(base+8<=k)decode8<T>(source,base,values);else for(size_t j=0;j<k-base;++j)values[j]=element(T,source,base+j);
    }
  }
  template<Type T> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt tiled capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    const size_t groups=(d.span+Rows-1)/Rows;
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(groups*SG*Subgroups),sycl::range<1>(SG*Subgroups))](sycl::handler& h) {
      sycl::local_accessor<float,1> xs(Tokens*Step,h);
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id(),local=it.get_local_linear_id();
        const size_t row0=it.get_group_linear_id()*Rows+sub*RowsPerSubgroup;const size_t n=std::min<size_t>(Tokens,d.count),k=d.k;
        const float* x=static_cast<const float*>(pointers[d.x]);const uint8_t* w=static_cast<const uint8_t*>(pointers[d.w]);
        float acc[RowsPerSubgroup][Tokens];
        #pragma unroll
        for(unsigned r=0;r<RowsPerSubgroup;++r){
          #pragma unroll
          for(unsigned t=0;t<Tokens;++t)acc[r][t]=0;}
        for(size_t step=0;step<k;step+=Step) {
          it.barrier(sycl::access::fence_space::local_space);
          for(unsigned i=local;i<Tokens*Step;i+=SG*Subgroups){const unsigned t=i/Step,c=i%Step;xs[t*Step+(c%8)*SG+c/8]=(t<n&&step+c<k)?x[t*k+step+c]:0.f;}
          it.barrier(sycl::access::fence_space::local_space);
          const size_t base=step+size_t(lane)*8;
          if(base>=k)continue;
          #pragma unroll
          for(unsigned r=0;r<RowsPerSubgroup;++r) {
            const size_t row=row0+r;if(row>=d.span)continue;
            float values[8];values8<T>(w+row*d.rb,base,k,values);
            if(base+8<=k) {
              #pragma unroll
              for(unsigned t=0;t<Tokens;++t){
                #pragma unroll
                for(unsigned j=0;j<8;++j){float input=xs[t*Step+j*SG+lane];float product=values[j]*input;acc[r][t]=acc[r][t]+product;}}
            } else {
              #pragma unroll
              for(unsigned t=0;t<Tokens;++t)for(unsigned j=0;j<8 && base+j<k;++j){float input=xs[t*Step+j*SG+lane];float product=values[j]*input;acc[r][t]=acc[r][t]+product;}
            }
          }
        }
        #pragma unroll
        for(unsigned r=0;r<RowsPerSubgroup;++r){
          #pragma unroll
          for(unsigned t=0;t<Tokens;++t){float sum=acc[r][t];
            for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
            if(lane==0&&t<n&&row0+r<d.span)static_cast<float*>(pointers[d.y])[t*d.span+row0+r]=sum;}}
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){
#define TILED_CASE(T) case Type::T:return run<Type::T>(q,p,deps)
TILED_CASE(F32);TILED_CASE(F16);TILED_CASE(BF16);TILED_CASE(Q8_0);TILED_CASE(Q6_K);
#undef TILED_CASE
    default:break;}
    throw std::invalid_argument("kopt tiled token rows: dense F32/F16/BF16/Q8_0/Q6_K only");
  }
};
// Dense token rows for raw formats (BF16/F16/F32 weights, F32 activations): one subgroup owns RW weight rows x T token
// rows; each 8-column weight chunk is decoded once and each activation chunk loaded once per subgroup. Every output keeps
// Multiply's single-row arithmetic (lane l owns columns l*8+SG*8*i, product then add in that order, the adjacent-pair
// tree). Requires 16-byte aligned rows (checked by the caller); BF16 without the explicit NaN-quiet test (finite weights
// are bit-identical, a NaN weight's product is the same quiet NaN). Prefill microbench, 16 tokens: HC low 91 -> 61 us.
template<unsigned RW,unsigned T> struct MultiplyRowsLean:ownrt::SyclOperation {
  static constexpr unsigned Subgroups=4;
  Descriptor desc{};
  template<Type W,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt lean rows capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    const size_t rtiles=(d.span+RW-1)/RW,ttiles=(d.count+T-1)/T,total=rtiles*ttiles,groups=(total+Subgroups-1)/Subgroups;
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(groups*SG*Subgroups),sycl::range<1>(SG*Subgroups))](sycl::handler& h) {
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
        const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
        const size_t row0=(logical/ttiles)*RW,tok0=(logical%ttiles)*T;
        const uint8_t* rows[RW];const float* xs[T];float acc[RW][T];
        #pragma unroll
        for(unsigned r=0;r<RW;++r){rows[r]=static_cast<const uint8_t*>(pointers[d.w])+(row0+r<d.span?row0+r:row0)*d.rb;
          #pragma unroll
          for(unsigned t=0;t<T;++t)acc[r][t]=0;}
        #pragma unroll
        for(unsigned t=0;t<T;++t)xs[t]=static_cast<const float*>(pointers[d.x])+(tok0+t<d.count?tok0+t:tok0)*d.k;
        const uint32_t k32=uint32_t(d.k);uint32_t base=lane*8u;
        for(;base+8u<=k32;base+=SG*8u) {
          float values[RW][8];
          #pragma unroll
          for(unsigned r=0;r<RW;++r) {
            if constexpr(W==Type::F32) {
              auto w=reinterpret_cast<const sycl::vec<uint32_t,4>*>(rows[r]+size_t(base)*4);auto lo=w[0],hi=w[1];
              #pragma unroll
              for(unsigned j=0;j<4;++j){values[r][j]=bits_float(lo[j]);values[r][j+4]=bits_float(hi[j]);}
            } else {
              auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(rows[r]+size_t(base)*2);
              #pragma unroll
              for(unsigned j=0;j<8;++j){if constexpr(W==Type::F16)values[r][j]=half(w[j]);else values[r][j]=bits_float(uint32_t(w[j])<<16);}
            }
          }
          #pragma unroll
          for(unsigned t=0;t<T;++t){float input[8];
            #pragma unroll
            for(unsigned j=0;j<8;++j)input[j]=xs[t][base+j];
            #pragma unroll
            for(unsigned r=0;r<RW;++r)
              #pragma unroll
              for(unsigned j=0;j<8;++j){float product=values[r][j]*input[j];acc[r][t]=acc[r][t]+product;}}
        }
        if(base<k32) {
          #pragma unroll
          for(unsigned r=0;r<RW;++r){float values[8];for(uint32_t j=0;base+j<k32;++j)values[j]=element(W,rows[r],base+j);
            #pragma unroll
            for(unsigned t=0;t<T;++t)for(uint32_t j=0;base+j<k32;++j){float product=values[j]*xs[t][base+j];acc[r][t]=acc[r][t]+product;}}
        }
        #pragma unroll
        for(unsigned r=0;r<RW;++r)
          #pragma unroll
          for(unsigned t=0;t<T;++t){float sum=acc[r][t];
            for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
            if(lane==0&&row0+r<d.span&&tok0+t<d.count)static_cast<float*>(pointers[d.y])[(tok0+t)*d.span+row0+r]=sum;}
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){case Type::BF16:return run<Type::BF16,32>(q,p,deps);case Type::F16:return run<Type::F16,32>(q,p,deps);case Type::F32:return run<Type::F32,32>(q,p,deps);default:break;}
    throw std::invalid_argument("kopt lean rows: raw formats only");
  }
};
inline bool lean_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_LEAN_ROWS");return !e||e[0]!='0';}();return on;}
// Several rows per subgroup (F32 activations, decode8 formats): one subgroup owns R consecutive rows of one slot, decodes
// each row straight from global memory (no local staging, no barrier) and shares each 8-column activation chunk across
// its rows. Every row keeps Multiply's single-row arithmetic exactly: lane l owns columns l*8+SG*8*i, the same decode8
// values, product then add in that order, the same adjacent-pair subgroup tree, and NaN for inactive rows.
template<unsigned R> struct MultiplyBlockRows:ownrt::SyclOperation {
  static constexpr unsigned Subgroups=4;
  Descriptor desc{};unsigned subgroup=32;
  template<Type T,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt block-rows capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    const size_t blocks=(d.span+R-1)/R,total=blocks*d.count,groups=(total+Subgroups-1)/Subgroups;
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(groups*SG*Subgroups),sycl::range<1>(SG*Subgroups))](sycl::handler& h) {
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
        const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
        const size_t slot=logical/blocks,first=(logical%blocks)*R;
        Route r{0,0,uint32_t(d.rows)};if(d.routed)r=static_cast<const Route*>(pointers[d.r])[slot];
        const bool valid=valid_route(r,d.experts,d.rows,d.span);
        if(d.routed&&first==0&&lane==0)static_cast<uint32_t*>(pointers[d.status])[slot]=valid?0:1;
        const float* x=static_cast<const float*>(pointers[d.x])+slot*d.k;const uint8_t* w=static_cast<const uint8_t*>(pointers[d.w]);
        float acc[R];const uint8_t* rows[R];bool live[R];
        #pragma unroll
        for(unsigned i=0;i<R;++i){acc[i]=0;const size_t row=first+i;live[i]=valid&&row<d.span&&row<r.row_count;
          rows[i]=live[i]?w+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb:w;}
        // Lean loop, same arithmetic: row pointers hoisted, a 32-bit column index, and a fixed-trip unrolled body for
        // every full 8-column chunk; the one ragged chunk per lane (if any) keeps the per-element checks.
        const uint32_t k32=uint32_t(d.k);uint32_t k=lane*8u;
        for(;k+8u<=k32;k+=SG*8u) {
          float input[8];
          #pragma unroll
          for(unsigned j=0;j<8;++j)input[j]=x[k+j];
          #pragma unroll
          for(unsigned i=0;i<R;++i) {
            if(!live[i])continue;float values[8];decode8<T>(rows[i],k,values);
            #pragma unroll
            for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}
          }
        }
        if(k<k32) {
          float input[8];for(unsigned j=0;k+j<k32;++j)input[j]=x[k+j];
          #pragma unroll
          for(unsigned i=0;i<R;++i) {
            if(!live[i])continue;float values[8];for(uint32_t j=0;k+j<k32;++j)values[j]=element(T,rows[i],k+j);
            for(unsigned j=0;k+j<k32;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}
          }
        }
        #pragma unroll
        for(unsigned i=0;i<R;++i) {
          float sum=acc[i];
          for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
          const size_t row=first+i;
          if(lane==0&&row<d.span)static_cast<float*>(pointers[d.y])[slot*d.span+row]=valid&&row<r.row_count?sum:bits_float(0x7fc00000);
        }
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){
#define BLOCK_CASE(T) case Type::T:return run<Type::T,32>(q,p,deps)
BLOCK_CASE(Q8_0);BLOCK_CASE(Q6_K);BLOCK_CASE(IQ2_S);BLOCK_CASE(IQ3_S);BLOCK_CASE(IQ4_NL);
#undef BLOCK_CASE
    default:break;}
    throw std::invalid_argument("kopt block rows: decode8 formats only");
  }
};
// HC gate + mix in one launch (2026-10-25, single-row decode). Work-group j runs the gate rows h*width+j (h=0..3) of
// hidden index j, one per subgroup, with Multiply's unchanged single-row code (dot, staging, adjacent-pair tree), and
// writes them. One lane then forms mix[j] exactly as the generic mix kernel (ng::mix): sum=0, sum=sum+sigmoid(gate)*norm
// for h=0..3, sum/4, with ng::sigmoid's 1/(1+detmath::exp(-x)). The separate hc_mix launch is skipped.
struct MultiplyMix:ownrt::SyclOperation {
  // J consecutive hidden indices per work-group: subgroup s runs row (s/J)*width + j0 + s%J, so each stream's J rows are
  // contiguous (as in Multiply's consecutive-row groups); lanes 0..J-1 of subgroup 0 then form the J mixes in parallel.
  static constexpr unsigned J=8;
  Descriptor desc{};size_t local_stride=16;uint32_t width=0;unsigned norm=0,mix=0;
  template<Type T,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;const uint32_t W=width;const unsigned ni=norm,mi=mix;const size_t stride=local_stride;
    if(W%J)throw std::invalid_argument("kopt gate+mix width");
    std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt gate+mix capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    return ownrt::prepared_submit(q,[=,range=sycl::nd_range<1>(sycl::range<1>(size_t(W/J)*SG*4*J),sycl::range<1>(SG*4*J))](sycl::handler& h) {
      sycl::local_accessor<uint8_t,1> storage(layout(T).elements==1?16:stride*4*J,h);sycl::local_accessor<float,1> gates(4*J,h);
      h.parallel_for(range,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),s=sg.get_group_linear_id(),stream=s/J,jj=s%J;
        const size_t j0=it.get_group_linear_id()*J,row=size_t(stream)*W+j0+jj;
        const uint8_t* source=static_cast<const uint8_t*>(pointers[d.w])+row*d.rb;
        const uint16_t* x=reinterpret_cast<const uint16_t*>(static_cast<const float*>(pointers[d.x]));
        auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+(layout(T).elements==1?0:s*stride);
        if(layout(T).elements!=1)stage_row<SG>(source,local,d.rb,lane);
        it.barrier(sycl::access::fence_space::local_space);
        float sum=dot<T,SG>(layout(T).elements==1?source:local,x,d.activation,d.k,lane);
        for(unsigned w=1;w<SG;w*=2){float rhs=sycl::select_from_group(sg,sum,(lane+w)%SG);if(lane%(2*w)==0)sum=sum+rhs;}
        if(lane==0){static_cast<float*>(pointers[d.y])[row]=sum;gates[s]=sum;}
        it.barrier(sycl::access::fence_space::local_space);
        if(s==0&&lane<J){
          const size_t j=j0+lane;const float* n=static_cast<const float*>(pointers[ni]);float m=0;
          for(unsigned g=0;g<4;++g)m=m+(1.f/(1.f+detmath::exp(-gates[g*J+lane])))*n[size_t(g)*W+j];
          static_cast<float*>(pointers[mi])[j]=m/4.f;
        }
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){
#define MIX_CASE(T) case Type::T:return run<Type::T,32>(q,p,deps)
MIX_CASE(F32);MIX_CASE(F16);MIX_CASE(BF16);MIX_CASE(Q8_0);MIX_CASE(Q6_K);MIX_CASE(IQ4_NL);
#undef MIX_CASE
    default:break;}
    throw std::invalid_argument("kopt gate+mix type");
  }
};
// Tensor-parallel expert placement (2026-10-25). Card `parity` computes only the slots whose expert id has that
// parity: RouteMask sets row_count=0 on the other slots (every routed kernel then skips them; the route stays valid).
// SlotSelect replaces the other slots' rows of the routed output with the peer card's (a bitwise copy).
struct RouteMask:ownrt::SyclOperation {
  // by_slot: split by slot position (every card holds every expert: exact 5/5 balance) instead of expert-id parity.
  uint32_t top=0,parity=0;bool by_slot=false;
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    auto* a=static_cast<Route*>(p[0]);auto* b=static_cast<Route*>(p[1]);const uint32_t n=top,par=parity;const bool slot=by_slot;
    return ownrt::prepared_submit(q,[=,range=sycl::range<1>(n)](sycl::handler& h){h.parallel_for(range,packet26::checked([=](sycl::id<1> i){
      const uint32_t key_a=slot?uint32_t(i[0]):a[i].expert_id,key_b=slot?uint32_t(i[0]):b[i].expert_id;
      if(key_a%2u!=par)a[i].row_count=0;if(key_b%2u!=par)b[i].row_count=0;}));});
  }
};
struct SlotSelect:ownrt::SyclOperation {
  uint32_t top=0,rows=0,parity=0;bool by_slot=false;
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    auto* y=static_cast<uint32_t*>(p[0]);const auto* peer=static_cast<const uint32_t*>(p[1]);const auto* ids=static_cast<const int32_t*>(p[2]);
    const uint32_t n=top,r=rows,par=parity;const bool by=by_slot;
    return ownrt::prepared_submit(q,[=,range=sycl::range<1>(size_t(n)*r)](sycl::handler& h){h.parallel_for(range,packet26::checked([=](sycl::id<1> i){
      const size_t slot=i[0]/r;const uint32_t key=by?uint32_t(slot):uint32_t(ids[slot]);if(key%2u!=par)y[i[0]]=peer[i[0]];}));});
  }
};
inline bool block_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_KOPT_BLOCK_ROWS");return !e||e[0]!='0';}();return on;}
Descriptor bind_matrix(ownrt::Device& d,Multiply& op,std::vector<ownrt::Allocation>& ids,Matrix m,
                uint32_t experts,uint32_t count,uint32_t span,ownrt::Allocation r=0,ownrt::Allocation status=0) {
  geometry(m.type,m.activation,m.output_type,m.rows,m.columns,op.subgroup);
  if(!experts || !count || !span || span>m.rows)throw std::invalid_argument("kopt routes");
  auto l=layout(m.type);size_t rb=mul(m.columns/l.elements,l.bytes);
  Descriptor v{m.type,m.activation,m.output_type,m.rows,m.columns,rb,op.groups,(mul(count,span)+3)/4,experts,count,span,r!=0,0,0,0,0,0,0,m.fp32!=0};
  auto add=[&](ownrt::Allocation id,size_t bytes){check(d,id,bytes);unsigned index=ids.size();ids.push_back(id);return index;};
  const size_t ab=m.activation==Type::F32?4:2;
  // A shared read-only input (fused siblings) binds once; outputs and weights must stay distinct.
  auto input=[&](ownrt::Allocation id,size_t bytes){for(unsigned i=0;i<ids.size();++i)if(ids[i]==id){check(d,id,bytes);return i;}return add(id,bytes);};
  v.w=add(m.w,mul(mul(experts,m.rows),rb));v.x=input(m.x,mul(mul(count,m.columns),ab));v.y=add(m.y,mul(mul(count,span),ab));
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
ownrt::Event gemv_mix(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,size_t rows,size_t k,Type a,Type o,unsigned sg,ownrt::Allocation norm,ownrt::Allocation mix,uint32_t width) {
  if(a!=Type::F32||o!=Type::F32||sg!=32||!width||rows!=size_t(width)*4)throw std::invalid_argument("kopt gate+mix: F32, 32 lanes, four stream rows per index");
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  auto desc=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,0},1,1,rows);
  check(d,norm,mul(rows,4));check(d,mix,mul(width,4));
  MultiplyMix fused;fused.desc=desc;fused.local_stride=op.local_stride;fused.width=width;
  fused.norm=unsigned(ids.size());ids.push_back(norm);fused.mix=unsigned(ids.size());ids.push_back(mix);
  if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
  return d.compute(fused,ids,{});
}
ownrt::Event route_mask(ownrt::Device& d,ownrt::Allocation routes,ownrt::Allocation routes_down,uint32_t top,uint32_t parity,bool by_slot) {
  check(d,routes,size_t(top)*sizeof(Route));check(d,routes_down,size_t(top)*sizeof(Route));if(routes==routes_down)throw std::invalid_argument("route mask aliases");
  RouteMask op;op.top=top;op.parity=parity;op.by_slot=by_slot;std::vector<ownrt::Allocation> ids{routes,routes_down};return d.compute(op,ids,{});
}
ownrt::Event slot_select(ownrt::Device& d,ownrt::Allocation y,ownrt::Allocation peer,ownrt::Allocation expert_ids,uint32_t top,uint32_t rows,uint32_t parity,bool by_slot) {
  check(d,y,size_t(top)*rows*4);check(d,peer,size_t(top)*rows*4);check(d,expert_ids,size_t(top)*4);
  if(y==peer||y==expert_ids||peer==expert_ids)throw std::invalid_argument("slot select aliases");
  SlotSelect op;op.top=top;op.rows=rows;op.parity=parity;op.by_slot=by_slot;std::vector<ownrt::Allocation> ids{y,peer,expert_ids};return d.compute(op,ids,{});
}
// Generation-2 token rows (prefill_reuse2.hpp): raw Q6_K/Q8_0 rows decoded 8 columns at a time exactly as MultiplyRows.
struct Reuse2Q6 {static void decode8(const uint8_t* row,uint32_t k,float (&v)[8]){kopt::decode8<Type::Q6_K>(row,k,v);}};
struct Reuse2Q8 {static void decode8(const uint8_t* row,uint32_t k,float (&v)[8]){kopt::decode8<Type::Q8_0>(row,k,v);}};
ownrt::Event gemv_tokens(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,size_t rows,size_t k,uint32_t tokens,Type a,Type o,unsigned sg) {
  if(!tokens||tokens>64)throw std::invalid_argument("kopt token rows 1..64");
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  op.desc[0]=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,0},1,tokens,rows);op.desc[0].row_major=true;
  if(a!=Type::F32||o!=Type::F32||tokens==1)return finish(d,op,ids);
  if(reuse2::enabled()&&sg==32&&k%8==0&&op.desc[0].rb<=UINT32_MAX&&(t==Type::BF16||t==Type::Q6_K||t==Type::Q8_0)&&(t!=Type::BF16||op.desc[0].rb%16==0)) {
    // OWNRT_PREFILL_REUSE2=1: RW rows x T tokens per subgroup (tile OWNRT_PREFILL_REUSE2_BF16 / _KOPT); every output keeps
    // MultiplyRowsLean's (BF16) or MultiplyRows' (Q6_K/Q8_0) single-row sequence and tree. Allocations are 16-byte aligned.
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    const uint32_t r32=uint32_t(rows),k32=uint32_t(k),rb=uint32_t(op.desc[0].rb);
    const unsigned c=t==Type::BF16?reuse2::config("BF16",reuse2::config_count,reuse2::default_bf16(r32,k32)):reuse2::config("KOPT",reuse2::config_count,reuse2::default_kopt(r32,k32));
    if(c<reuse2::config_count) {
      if(t==Type::BF16)return reuse2::issue<reuse2::BF16x8,REUSE2_CONFIGS>(d,c,ids,r32,k32,tokens,rb);
      if(t==Type::Q6_K)return reuse2::issue<reuse2::Decode8<Reuse2Q6>,REUSE2_CONFIGS>(d,c,ids,r32,k32,tokens,rb);
      return reuse2::issue<reuse2::Decode8<Reuse2Q8>,REUSE2_CONFIGS>(d,c,ids,r32,k32,tokens,rb);
    }
  }
  if(sg==32&&tokens<=16&&prefill_switches::tiled_rows()){
    // F32 token rows (up to 16): tiled kernel, activations staged once per 16 weight rows.
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    MultiplyTiled<2,16> tiled;tiled.desc=op.desc[0];return d.compute(tiled,ids,{});
  }
  if(!prefill_switches::small_tile_rows())return finish(d,op,ids);
  if(lean_rows()&&sg==32&&(t==Type::BF16||t==Type::F16||t==Type::F32)&&op.desc[0].rb%16==0&&op.matrices==1) {
    // Raw weights: 2 weight rows x 4 token rows per subgroup (register tile; prefill microbench HC low 91 -> 61 us).
    MultiplyRowsLean<2,4> lean;lean.desc=op.desc[0];
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    return d.compute(lean,ids,{});
  }
  // F32 token rows: weight-reuse kernel, 4 token rows per subgroup (small register tile, after vllm-xpu-kernels PR #22).
  constexpr unsigned R=4;MultiplyRows<R> rows_op;rows_op.desc=op.desc[0];rows_op.subgroup=sg;rows_op.local_stride=op.local_stride;
  rows_op.desc.first_group=0;rows_op.groups=(rows*((tokens+R-1)/R)+rows_per_group-1)/rows_per_group;
  if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
  return d.compute(rows_op,ids,{});
}
ownrt::Event routed_gemv(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,ownrt::Allocation r,ownrt::Allocation status,uint32_t experts,uint32_t rows,size_t k,uint32_t count,uint32_t span,Type a,Type o,unsigned sg,ownrt::Allocation fp32) {
  if(!r || !status)throw std::invalid_argument("kopt routing handles required");
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  op.desc[0]=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,fp32},experts,count,span,r,status);
  if(a==Type::F32&&o==Type::F32&&sg==32&&!fp32&&block_rows()&&(t==Type::IQ2_S||t==Type::IQ3_S||t==Type::Q8_0||t==Type::Q6_K)) { // not IQ4_NL: K=640 loses parallelism (153 vs ~107 us/layer)
    // F32 routed rows: 4 rows per subgroup, decoded from global memory (OWNRT_KOPT_BLOCK_ROWS=0 keeps one row each).
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    // OWNRT_SMALLK_ROWS=1|2: rows per subgroup for K <= 640 (same per-row arithmetic); default 4.
    static const int small_k=[]{const char* e=std::getenv("OWNRT_SMALLK_ROWS");return e?std::atoi(e):4;}();
    if(k<=640&&small_k==2){MultiplyBlockRows<2> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    if(k<=640&&small_k==1){MultiplyBlockRows<1> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    MultiplyBlockRows<4> block;block.desc=op.desc[0];return d.compute(block,ids,{});
  }
  if(a==Type::F32&&o==Type::F32&&sg==32&&!fp32&&block_rows()&&t==Type::IQ4_NL) {
    // IQ4_NL (K=640): one row per subgroup straight from global memory with the word decoder (microbench 99 -> 73 us).
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    // Rows per subgroup (same per-row arithmetic). With the lean loop 2 is fastest (engine profile, IQ4_NL down per
    // step: 1 row 1135 us, 2 rows 1049, 4 rows 1123); OWNRT_IQ4NL_ROWS=1|4 overrides.
    static const int rows=[]{const char* e=std::getenv("OWNRT_IQ4NL_ROWS");return e?std::atoi(e):2;}();
    if(rows==2){MultiplyBlockRows<2> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    if(rows==4){MultiplyBlockRows<4> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    MultiplyBlockRows<1> block;block.desc=op.desc[0];return d.compute(block,ids,{});
  }
  return finish(d,op,ids);
}
ownrt::Event fused_gemv(ownrt::Device& d,const std::vector<Matrix>& matrices,unsigned sg) {
  if(matrices.empty() || matrices.size()>4)throw std::invalid_argument("kopt fused matrix count1..4");
  Multiply op;op.subgroup=sg;op.matrices=matrices.size();std::vector<ownrt::Allocation> ids;
  for(size_t i=0;i<matrices.size();++i)op.desc[i]=bind_matrix(d,op,ids,matrices[i],1,1,matrices[i].rows);
  return finish(d,op,ids);
}
}
