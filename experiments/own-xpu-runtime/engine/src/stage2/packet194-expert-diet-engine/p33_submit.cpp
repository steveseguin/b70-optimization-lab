#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/p33_submit.hpp"
#include "stage2/packet194-expert-diet-engine/p33_candidates.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/p33_dense_v2.hpp"
#include "stage2/packet194-expert-diet-engine/p33_dense_raw.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/prefill_switches.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prefill_reuse2_op.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/p42_expert.hpp"
#include "stage2/packet194-expert-diet-engine/expert_down.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p33 {
template<unsigned Mode,iq3::Type T,unsigned K,unsigned Split=1,bool F=false> struct Kernel final:
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
  for(unsigned slot=0;slot<d.count*d.tokens;++slot){
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
      else if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S){auto pair=Mode==2?p42expert::gate_lane<T,K>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane):expert_lane<T,K,true>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane);sums[0][lane]=pair[0];sums[1][lane]=pair[1];}
      else sums[0][lane]=dense_lane<T,K,F>(d.w+source,d.x+size_t(slot)*K*(F?2:1),unsigned(range.first),unsigned(range.second),lane);
     }
     for(unsigned j=0;j<(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1);++j)parts[j][part]=iq3::tree32(sums[j]);
    }
    for(unsigned j=0;j<(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1);++j){float v=Split==1?parts[j][0]:(parts[j][0]+parts[j][1])+(parts[j][2]+parts[j][3]);float out=valid?v:iq3::bits_float(0x7fc00000);if constexpr(F)reinterpret_cast<float*>(j?d.py:d.y)[slot*d.rows+row]=out;else (j?d.py:d.y)[slot*d.rows+row]=iq3::bf16_bits(out);}
   }
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto d=bind(p);
  const size_t groups=size_t(d.rows)*d.count*d.tokens*Split;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(groups*32,32)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),item=unsigned(it.get_group_linear_id()),logical=item/Split,part=item%Split;
   const unsigned row=d.tokens>1?logical/d.tokens:logical%d.rows,slot=d.tokens>1?logical%d.tokens:logical/d.rows;
   iq3::Route r{0,0,d.rows};if(d.routes)r=d.routes[slot];const bool ok=iq3::valid_route(r,d.experts,d.rows,d.rows),valid=ok&&row<r.row_count;
   std::array<float,2> sums{};
   if(valid){const unsigned source=(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb);auto range=iq3::kopt2::bounds(K,part,Split);
    if constexpr(T==iq3::Type::IQ4_NL)sums[0]=down_lane<Mode,K>(d.w+source,d.x+slot*K,lane);
    else if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S)sums=Mode==2?p42expert::gate_lane<T,K>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane):expert_lane<T,K,true>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane);
    else sums[0]=dense_lane<T,K,F>(d.w+source,d.x+size_t(slot)*K*(F?2:1),unsigned(range.first),unsigned(range.second),lane);
   }
   constexpr unsigned projections=T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1;
   for(unsigned j=0;j<projections;++j){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sums[j],(lane+width)%32);if(lane%(2*width)==0)sums[j]=sums[j]+rhs;}
    if(lane==0){float v=valid?sums[j]:iq3::bits_float(0x7fc00000);if constexpr(Split==1){const unsigned out=slot*d.rows+row;if constexpr(F)reinterpret_cast<float*>(j?d.py:d.y)[out]=v;else (j?d.py:d.y)[out]=iq3::bf16_bits(v);}else d.scratch[(logical*2+j)*4+part]=v;}}
   if(lane==0&&row==0&&part==0&&d.routes){d.status[slot]=!ok;if constexpr(projections==2)d.ps[slot]=!ok;}
  })));});
 }
#endif
};
#ifndef OWN_RT_HOST_ONLY
struct Finish final:ownrt::SyclOperation {unsigned n;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto s=static_cast<const float*>(p[0]);auto y=static_cast<uint16_t*>(p[1]);unsigned count=n;return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(count)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked([=](sycl::id<1> id){auto v=s+id[0]*8;y[id[0]]=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));})));});}
};
 #endif
template<unsigned Mode,iq3::Type T,unsigned K,unsigned Split,bool F=false> integrated::Launch issue(ownrt::Device& d,const std::vector<integrated::Matrix>& ms){
 static_assert(!F||(Mode==0&&Split==1&&T!=iq3::Type::IQ4_NL&&T!=iq3::Type::IQ2_S&&T!=iq3::Type::IQ3_S),"exact F32 activations: dense split1 only");
 const auto& m=ms[0];const auto& peer=ms.size()==2?ms[1]:m;Kernel<Mode,T,K,Split,F> k;
 k.b.rb=integrated::arithmetic::row_bytes(T,K,T==iq3::Type::F32||T==iq3::Type::BF16?(Split==4?4:0):(Split==4?7:(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0?6:2)));k.b.rows=m.rows;k.b.count=m.count;k.b.experts=m.experts;k.b.has_routes=bool(m.routes);k.b.tokens=m.tokens;
 if(m.tokens!=1&&(Mode!=0||Split!=1||m.routes||m.count!=1||ms.size()!=1))throw std::invalid_argument("p33 token rows: dense split1 only");
 if(uint64_t(m.experts)*m.rows*k.b.rb>UINT32_MAX)throw std::invalid_argument("p33 32-bit row offset overflow");
 std::array<ownrt::Allocation,9> ids{m.w,peer.w,m.x,m.y,peer.y,m.routes?m.routes:m.x,m.status?m.status:m.y,peer.status?peer.status:peer.y,m.workspace};auto e=d.compute(k,ids,{});integrated::Launch r{e,e,1};

#ifndef OWN_RT_HOST_ONLY
 if constexpr(Split==4){Finish f;f.n=m.rows*m.count;std::array a{m.workspace,m.y};std::array after{e};r.last=d.compute(f,a,after);r.passes=2;}
#endif
 return r;
}
#ifndef OWN_RT_HOST_ONLY
// Dense token rows with weight reuse (F32 activations, split 1): one subgroup owns one weight row and a tile of R token
// rows. Each expanded value scale*code is computed once and applied to every token of the tile; each token keeps
// dense_lane's exact sequence (lane tiles of 8, value then product then add) and the adjacent-pair subgroup tree.
template<iq3::Type T,unsigned K,unsigned R> struct DenseRows final:ownrt::SyclOperation {
 p28::Bound b{};
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto d=b;d.w=static_cast<const uint8_t*>(p[0]);d.x=static_cast<const uint16_t*>(p[1]);d.y=static_cast<uint16_t*>(p[2]);
  const size_t tiles=(d.tokens+R-1)/R,groups=size_t(d.rows)*tiles;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(groups*32,32)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const unsigned row=unsigned(logical/tiles),first=unsigned((logical%tiles)*R),n=std::min<unsigned>(R,d.tokens-first);
   const uint8_t* w=d.w+size_t(row)*unsigned(d.rb);const float* x=reinterpret_cast<const float*>(d.x)+size_t(first)*K;
   float sums[R];for(unsigned r=0;r<R;++r)sums[r]=0;
   for(unsigned tile=lane*8;tile<K;tile+=256){
    constexpr unsigned group=T==iq3::Type::Q6_K?16:32;
    const float scale=iq3::bits_float(iq3::u32(w+K+4*(tile/group)));
    #pragma unroll
    for(unsigned j=0;j<8;++j){
     float value=scale*float(iq3::signed8(w[tile+j]));
     for(unsigned r=0;r<R;++r)if(r<n){float input=x[size_t(r)*K+tile+j];float product=value*input;sums[r]=sums[r]+product;}
    }
   }
   for(unsigned r=0;r<R;++r){float sum=sums[r];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    if(lane==0&&r<n)reinterpret_cast<float*>(d.y)[size_t(first+r)*d.rows+row]=sum;}
  })));});
 }
};
#endif
#ifndef OWN_RT_HOST_ONLY
// OWNRT_DENSE_DECODE_V2=1 (lab 2026-10-26, default off): decode rows of the expanded Q8_0 6144-column matrices (the
// attention output projections), two rows per subgroup, p33_dense_v2.hpp. Same values as Kernel<0,T,K,1,true>.
template<iq3::Type T,unsigned K,unsigned R,unsigned U> struct DenseV2 final:ownrt::SyclOperation {
 uint32_t rows=0,rb=0;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const uint8_t* w=static_cast<const uint8_t*>(p[0]);const float* x=static_cast<const float*>(p[1]);float* y=static_cast<float*>(p[2]);
  const uint32_t n=rows,b=rb;const size_t global=(size_t((n+R-1)/R)*32+127)/128*128;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(global,128)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   v2::dense_rows<T,K,R,U>(w,x,y,n,b,it);})));});
 }
};
inline bool v2_aligned(ownrt::Device& d,ownrt::Allocation a,uintptr_t n){return reinterpret_cast<uintptr_t>(d.arena.row(a).pointer)%n==0;}
// OWNRT_DENSE_RAW=1 (lab 2026-10-26, default off): raw-size Q6_K / Q8_0 rows (dense_raw.hpp), p33_dense_raw.hpp kernels.
template<iq3::Type T,unsigned K,unsigned R,unsigned U,unsigned G> struct DenseRaw final:ownrt::SyclOperation {
 uint32_t rows=0,rb=0,tokens=1;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const uint32_t groups=(rows+R-1)/R;const size_t global=(size_t(groups)*tokens*32+127)/128*128;
  const raw::RowsKernel<T,K,R,U,G> kernel{static_cast<const uint8_t*>(p[0]),static_cast<const float*>(p[1]),static_cast<float*>(p[2]),rows,rb,groups,tokens};
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(global,128)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked(kernel)));});
 }
};
template<iq3::Type T,unsigned K,unsigned R,unsigned U,unsigned G> ownrt::Event raw_rows(ownrt::Device& d,const integrated::Matrix& m,uint32_t rb){
 DenseRaw<T,K,R,U,G> op;op.rows=uint32_t(m.rows);op.rb=rb;op.tokens=m.tokens;std::array<ownrt::Allocation,3> ids{m.w,m.x,m.y};return d.compute(op,ids,{});
}
// OWNRT_DRAFT_HEAD_RAW=1 (default off): the rank-0 draft head prefix, raw Q6_K rows with BF16 activations and outputs.
template<unsigned K,unsigned R,unsigned U> struct DenseRawBF16 final:ownrt::SyclOperation {
 uint32_t rows=0,rb=0;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const size_t global=(size_t((rows+R-1)/R)*32+127)/128*128;
  const raw::RowsKernelBF16<K,R,U> kernel{static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),rows,rb};
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(global,128)](sycl::handler& h){h.parallel_for(p35_range0,p28::checked(packet26::checked(kernel)));});
 }
};
template<iq3::Type T,unsigned K> integrated::Launch raw_issue(ownrt::Device& d,const std::vector<integrated::Matrix>& ms,unsigned v){
 const auto& m=ms.at(0);
 if constexpr(T==iq3::Type::Q6_K&&K==2560) if(denseraw::draft_head()&&ms.size()==1&&v==6&&m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&m.tokens==1) {
  if(m.fp32||m.routes||m.status||m.count!=1||m.experts!=1||(m.span&&m.span!=m.rows)||!m.rows||m.rows>UINT32_MAX||m.columns!=K)throw std::invalid_argument("p33 raw BF16: dense split-1 rows only");
  const size_t rb=denseraw::row_bytes(T,K);
  if(d.arena.row(m.w).bytes<size_t(m.rows)*rb||!v2_aligned(d,m.w,4)||!v2_aligned(d,m.x,16)||!v2_aligned(d,m.y,2))throw std::invalid_argument("p33 raw BF16: weight extent/alignment");
  DenseRawBF16<K,1,1> op;op.rows=uint32_t(m.rows);op.rb=uint32_t(rb);std::array<ownrt::Allocation,3> ids{m.w,m.x,m.y};auto e=d.compute(op,ids,{});return {e,e,1};
 }
 if(ms.size()!=1||v!=6||m.activation!=iq3::Type::F32||m.output_type!=iq3::Type::F32||m.fp32||m.routes||m.status||m.count!=1||m.experts!=1||(m.span&&m.span!=m.rows)||!m.rows||m.rows>UINT32_MAX||!m.tokens||m.columns!=K)
  throw std::invalid_argument("p33 raw: dense F32 split-1 rows only");
 if constexpr(!((T==iq3::Type::Q6_K&&K==2560)||(T==iq3::Type::Q8_0&&K==6144)))throw std::invalid_argument("p33 raw: uncompiled shape");
 else {
  const size_t rb=denseraw::row_bytes(T,K);
  if(d.arena.row(m.w).bytes<size_t(m.rows)*rb||rb%4||!v2_aligned(d,m.w,4)||!v2_aligned(d,m.x,16)||!v2_aligned(d,m.y,4))throw std::invalid_argument("p33 raw: weight extent/alignment");
  if(m.tokens>1&&reuse2::enabled()) {
   // Generation-2 token rows (OWNRT_PREFILL_REUSE2=1; tile OWNRT_PREFILL_REUSE2_P33=i, config_count = the raw row kernel).
   const unsigned c=reuse2::config("P33",reuse2::config_count,reuse2::default_p33(uint32_t(m.rows),K));
   if(c<reuse2::config_count){std::array<ownrt::Allocation,3> ids{m.w,m.x,m.y};auto e=reuse2::issue<raw::Reuse2Raw<T>,REUSE2_CONFIGS>(d,c,ids,uint32_t(m.rows),K,m.tokens,uint32_t(rb));return {e,e,1};}
  }
  // Defaults measured on card 27 (research/dense-raw/RESULT.md): Q6_K 1 row x 1 block pair, Q8_0 1 row x 2 tiles, 128 GRF.
  const unsigned rug=raw::config(T,T==iq3::Type::Q6_K?111u:121u);ownrt::Event e{};
  switch(rug){
   case 111:e=raw_rows<T,K,1,1,128>(d,m,uint32_t(rb));break;
   case 121:e=raw_rows<T,K,1,2,128>(d,m,uint32_t(rb));break;
   case 141:e=raw_rows<T,K,1,4,128>(d,m,uint32_t(rb));break;
   case 211:e=raw_rows<T,K,2,1,128>(d,m,uint32_t(rb));break;
   case 221:e=raw_rows<T,K,2,2,128>(d,m,uint32_t(rb));break;
   case 411:e=raw_rows<T,K,4,1,128>(d,m,uint32_t(rb));break;
   case 412:e=raw_rows<T,K,4,1,256>(d,m,uint32_t(rb));break;
   case 811:e=raw_rows<T,K,8,1,128>(d,m,uint32_t(rb));break;
   default:throw std::invalid_argument("OWNRT_DENSE_RAW_Q6/Q8: 111, 121, 141, 211, 221, 411, 412 or 811");
  }
  return {e,e,1};
 }
}
#endif
template<iq3::Type T,unsigned K> integrated::Launch dense_issue(ownrt::Device& d,const std::vector<integrated::Matrix>& m,unsigned v){
#ifndef OWN_RT_HOST_ONLY
 if constexpr(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0) if(m.at(0).raw)return raw_issue<T,K>(d,m,v);
#endif
 if(m.at(0).raw)throw std::invalid_argument("p33 raw rows: device Q6_K/Q8_0 only");
#ifndef OWN_RT_HOST_ONLY
 if constexpr(T==iq3::Type::Q8_0&&K==6144) if(v2::enabled()&&m.size()==1&&v==6&&m[0].activation==iq3::Type::F32&&m[0].output_type==iq3::Type::F32&&m[0].tokens==1&&m[0].count==1&&
   m[0].experts==1&&!m[0].routes&&!m[0].status&&m[0].rows<=UINT32_MAX&&v2_aligned(d,m[0].w,16)&&v2_aligned(d,m[0].x,16)) {
  const size_t rb=integrated::arithmetic::row_bytes(T,K,6);
  if(rb%4==0&&rb<=UINT32_MAX){DenseV2<T,K,2,2> op;op.rows=uint32_t(m[0].rows);op.rb=uint32_t(rb);std::array<ownrt::Allocation,3> ids{m[0].w,m[0].x,m[0].y};auto e=d.compute(op,ids,{});return {e,e,1};}
 }
 if constexpr(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0) if(m[0].activation==iq3::Type::F32&&m[0].tokens>1&&v==6&&reuse2::enabled()) {
  // Generation-2 token rows (OWNRT_PREFILL_REUSE2=1; tile OWNRT_PREFILL_REUSE2_P33=i): dense_lane's values and sequence.
  const size_t rb=integrated::arithmetic::row_bytes(T,K,6);
  const unsigned c=reuse2::config("P33",reuse2::config_count,reuse2::default_p33(uint32_t(m[0].rows),K));
  if(c<reuse2::config_count&&rb%4==0&&K%4==0&&reuse2::aligned(d,m[0].w,4)&&reuse2::aligned(d,m[0].x,16)&&rb<=UINT32_MAX) {
   std::array<ownrt::Allocation,3> ids{m[0].w,m[0].x,m[0].y};
   auto e=reuse2::issue<reuse2::Expanded8<T==iq3::Type::Q6_K?16u:32u>,REUSE2_CONFIGS>(d,c,ids,uint32_t(m[0].rows),K,m[0].tokens,uint32_t(rb));
   return {e,e,1};
  }
 }
 if constexpr(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0) if(m[0].activation==iq3::Type::F32&&m[0].tokens>1&&v==6&&prefill_switches::weight_reuse_rows()) {
  constexpr unsigned R=4;DenseRows<T,K,R> k;k.b.rb=integrated::arithmetic::row_bytes(T,K,6);k.b.rows=m[0].rows;k.b.tokens=m[0].tokens;
  std::array<ownrt::Allocation,3> ids{m[0].w,m[0].x,m[0].y};auto e=d.compute(k,ids,{});return {e,e,1};
 }
#endif
 if(m[0].activation==iq3::Type::F32){if(v==7||v==4)throw std::invalid_argument("p33 exact F32 mode has no split4 variant");return issue<0,T,K,1,true>(d,m);}
 return v==7||v==4?issue<0,T,K,4>(d,m):issue<0,T,K,1>(d,m);}
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
 if(m.at(0).tokens!=1&&name!="p33.dense.segment")throw std::invalid_argument("p33 token rows: dense segment only");
 if(name=="p33.down.bank"||name=="p33.down.select"){
  p29::validate(d,m,"p29.down.wg32",shared,variant);
  return name=="p33.down.bank"?issue<0,iq3::Type::IQ4_NL,640,1>(d,m):issue<1,iq3::Type::IQ4_NL,640,1>(d,m);
 }
 if(name=="p42.gate.packed"){
  p28::validate(d,m,"p28.paired.wg32",shared,variant);
  if(m[0].type==iq3::Type::IQ2_S)return issue<2,iq3::Type::IQ2_S,2560,1>(d,m);
  if(m[0].type==iq3::Type::IQ3_S)return issue<2,iq3::Type::IQ3_S,2560,1>(d,m);
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
