#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#pragma once
// OWNRT_DRAFT_CHUNK_BATCH=1 (2026-10-30, research/tp/prefill-draft-batch-2026-10-30; default off): the KV-only draft
// prompt rows of one prefill chunk as one launch per site over all rows (mtp.hpp replay_chunk_batch), instead of 15
// single-row commands per row. Each kernel here computes every output with the unchanged single-row arithmetic of
// the kernel the draft's row path runs at that site; only which work-item computes which (row, token) output changes:
// - NormTokens: p59::Norm (one 256-item group per normalised row, same tree, rsqrt, products), token-major rows, the
//   gain of the row within its token.
// - DenseTokens<K>: p59::Dense<K,false,false,1,1> (and DenseBatch4, whose outputs keep that sequence): one subgroup per
//   output, p59::lane<K,false> for its weight row and input row, the same 32-lane adjacent tree, bf16 output, and
//   p59::tail()'s low / merge_add expressions (merge_add adds the token's own row of `other`). A subgroup runs R
//   consecutive weight rows for one input row (each output its own lane() call) and consecutive subgroups take
//   consecutive input rows of the same weight rows, so weights and inputs are reused from cache.
// - DenseSplitTokens<K,Split>: p59::Dense<K,false,false,1,Split> (Split*32 items per output: Dense::chain per part,
//   the subgroup tree, then the parts' tree in local memory), one work-group per (weight row, input row).
// - GateTokens<K>: mtp36 Dense<K,0,false> (BF16 production projection): its 32 lane sums p28::dense_lane<BF16,K>
//   reduced by the same adjacent tree (iq3::tree32 is that tree), computed by one work-item per output.
// - MixTokens: mtp36 Elements<mix> per (token, element), with its active / sticky-error guard.
#include "stage2/packet194-expert-diet-engine/p59_draft.hpp"
#include "stage2/packet194-expert-diet-engine/p28/dense.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace draftbatch {
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
using ownrt::Allocation;
inline float widen(uint16_t b){return iq3::bits_float(uint32_t(b)<<16);}
// The 32-lane adjacent-pair tree of the subgroup reductions (select_from_group(sum, l+w), lanes l % 2w == 0 add).
inline float tree32(float* s){for(unsigned w=1;w<32;w*=2)for(unsigned j=0;j<32;j+=2*w)s[j]=s[j]+s[j+w];return s[0];}
inline void extent(ownrt::Device& d,Allocation a,size_t n){const auto& r=d.arena.row(a);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<n)throw std::invalid_argument("draft batch extent/lifetime");}

// x, y: tokens*rows rows of width BF16 (token-major); gain: rows*width F32 (row r of every token uses gain row r).
struct NormTokens final:Base {unsigned tokens=0,rows=0,width=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto x=static_cast<const uint16_t*>(p[0]);auto gain=static_cast<const float*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);
  for(unsigned g=0;g<tokens*rows;++g){const unsigned row=g%rows,n=width;float s[256]{};for(unsigned l=0;l<256;++l)for(unsigned k=l;k<n;k+=256){float v=widen(x[g*n+k]);s[l]+=v*v;}
   for(unsigned w=1;w<256;w*=2)for(unsigned l=0;l<256;l+=2*w)s[l]+=s[l+w];float inv=detmath::rsqrt(s[0]/float(n)+1e-6f);
   for(unsigned k=0;k<n;++k)y[g*n+k]=iq3::bf16_bits((widen(x[g*n+k])*inv)*gain[row*n+k]);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&)const override {
  auto x=static_cast<const uint16_t*>(p[0]);auto gain=static_cast<const float*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);const unsigned R=rows,n=width;const size_t groups=size_t(tokens)*rows;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(groups*256,256)](sycl::handler& h){sycl::local_accessor<float,1>s(256,h);h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it){
   const unsigned l=it.get_local_linear_id(),g=unsigned(it.get_group_linear_id()),row=g%R,base=g*n;float sum=0;
   for(unsigned k=l;k<n;k+=256){float v=widen(x[base+k]);sum+=v*v;}s[l]=sum;it.barrier(sycl::access::fence_space::local_space);
   for(unsigned w=1;w<256;w*=2){if(l%(2*w)==0)s[l]+=s[l+w];it.barrier(sycl::access::fence_space::local_space);}
   float inv=detmath::rsqrt(s[0]/float(n)+1e-6f);for(unsigned k=l;k<n;k+=256)y[base+k]=iq3::bf16_bits((widen(x[base+k])*inv)*gain[row*n+k]);}));});}
#endif
};
inline integrated::Launch norm(ownrt::Device&d,Allocation x,Allocation gain,Allocation y,unsigned tokens,unsigned rows,unsigned width){
 if(!tokens||!rows||!width||width>10240||size_t(tokens)*rows*width>=(size_t(1)<<31))throw std::invalid_argument("draft batch norm shape");
 extent(d,x,size_t(tokens)*rows*width*2);extent(d,gain,size_t(rows)*width*4);extent(d,y,size_t(tokens)*rows*width*2);
 NormTokens op;op.tokens=tokens;op.rows=rows;op.width=width;std::array ids{x,gain,y};auto e=d.compute(op,ids,{});return {e,e,1};}

// One linear site over `slots` input rows (token-major; per_token slots per token): y[slot*rows+row] as p59::Dense writes
// output i = slot*rows+row of a batch of `slots` rows, and the tail into out[slot*rows+row]; merge_add's other row is
// other[(slot/per_token)*rows + row] (the token's own row; one token's site reads other[i % rows]).
struct Tokens {Allocation w{},x{},y{},out{},other{};unsigned rows=0,slots=0,per_token=1;p59::Tail tail=p59::none;};
struct TokensBound {const uint8_t* w;const uint16_t* x;uint16_t* y;uint16_t* out;const uint16_t* other;unsigned rows,slots,per_token;p59::Tail tail;};
inline TokensBound bind_tokens(const Tokens& a,std::span<void*const>p){return {static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),
 static_cast<uint16_t*>(p[3]),static_cast<const uint16_t*>(p[4]),a.rows,a.slots,a.per_token,a.tail};}
inline void tail(const TokensBound& b,unsigned slot,unsigned row,uint16_t value){const unsigned i=slot*b.rows+row;
 b.y[i]=value; // p59::tail()
 if(b.tail==p59::low)b.out[i]=iq3::bf16_bits(ng::silu(widen(value)/4.f));
 if(b.tail==p59::merge_add)b.out[i]=iq3::bf16_bits(widen(value)+widen(b.other[(slot/b.per_token)*b.rows+row]));}
template<unsigned K,unsigned R> struct DenseTokens final:Base {Tokens a;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto b=bind_tokens(a,p);
  for(unsigned slot=0;slot<b.slots;++slot)for(unsigned row=0;row<b.rows;++row){float s[32];for(unsigned l=0;l<32;++l)s[l]=p59::lane<K,false>(b.w+size_t(row)*K*2,b.x+size_t(slot)*K,l,0,K);
   tail(b,slot,row,iq3::bf16_bits(tree32(s)));}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&)const override {auto b=bind_tokens(a,p);
  const unsigned groups=b.rows/R,S=b.slots;const size_t subgroups=size_t(groups)*S;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(((subgroups*32+255)/256)*256,256)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned l=sg.get_local_linear_id();if(it.get_global_linear_id()/32>=subgroups)return;
    const unsigned id=unsigned(it.get_global_linear_id()/32),slot=id%S,row0=(id/S)*R;const uint16_t* x=b.x+slot*K; // 32-bit index math (subgroups < 2^31)
    float sum[R];
    #pragma unroll
    for(unsigned r=0;r<R;++r)sum[r]=p59::lane<K,false>(b.w+(row0+r)*(K*2),x,l,0,K);
    #pragma unroll
    for(unsigned r=0;r<R;++r)for(unsigned w=1;w<32;w*=2){float rhs=sycl::select_from_group(sg,sum[r],(l+w)%32);if(l%(2*w)==0)sum[r]+=rhs;}
    if(l==0)for(unsigned r=0;r<R;++r)tail(b,slot,row0+r,iq3::bf16_bits(sum[r]));
   }));});}
#endif
};
template<unsigned K,unsigned Split> struct DenseSplitTokens final:Base {Tokens a;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto b=bind_tokens(a,p);using D=p59::Dense<K,false,false,1,Split>;
  for(unsigned slot=0;slot<b.slots;++slot)for(unsigned row=0;row<b.rows;++row){float parts[Split];
   for(unsigned part=0;part<Split;++part){float s[32];for(unsigned l=0;l<32;++l)s[l]=D::chain(b.w+size_t(row)*K*2,b.x+size_t(slot)*K,l,part);parts[part]=tree32(s);}
   for(unsigned w=1;w<Split;w*=2)for(unsigned j=0;j<Split;j+=2*w)parts[j]+=parts[j+w];tail(b,slot,row,iq3::bf16_bits(parts[0]));}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&)const override {auto b=bind_tokens(a,p);using D=p59::Dense<K,false,false,1,Split>;
  const unsigned S=b.slots;const size_t n=size_t(b.rows)*S;constexpr unsigned wg=Split*32;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(n*wg,wg)](sycl::handler& h){sycl::local_accessor<float,1> partial(Split,h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned physical=unsigned(it.get_local_linear_id())%32,part=unsigned(it.get_local_linear_id())/32,i=unsigned(it.get_group_linear_id());
    const unsigned slot=i%S,row=i/S;
    float sum=D::chain(b.w+row*(K*2),b.x+slot*K,physical,part);
    const unsigned base=sg.get_local_linear_id()-physical;
    for(unsigned w=1;w<32;w*=2){float r=sycl::select_from_group(sg,sum,base+(physical+w)%32);if(physical%(2*w)==0)sum+=r;}
    if(!physical)partial[part]=sum;it.barrier(sycl::access::fence_space::local_space);
    if(it.get_local_linear_id()==0){for(unsigned w=1;w<Split;w*=2)for(unsigned j=0;j<Split;j+=2*w)partial[j]+=partial[j+w];tail(b,slot,row,iq3::bf16_bits(partial[0]));}
   }));});}
#endif
};
template<unsigned K> struct GateTokens final:Base {Tokens a;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto b=bind_tokens(a,p);
  for(unsigned slot=0;slot<b.slots;++slot)for(unsigned row=0;row<b.rows;++row){float s[32];for(unsigned l=0;l<32;++l)s[l]=p28::dense_lane<iq3::Type::BF16,K>(b.w+size_t(row)*K*2,b.x+size_t(slot)*K,0,K,l);
   b.y[slot*b.rows+row]=iq3::bf16_bits(tree32(s));}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&)const override {auto b=bind_tokens(a,p);
  const unsigned S=b.slots;const size_t n=size_t(b.rows)*S;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(((n+255)/256)*256,256)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it){
    if(it.get_global_linear_id()>=n)return;const unsigned i=unsigned(it.get_global_linear_id()),slot=i%S,row=i/S;
    const uint8_t* w=b.w+row*(K*2);const uint16_t* x=b.x+slot*K;float s[32];
    for(unsigned l=0;l<32;++l)s[l]=p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);
    b.y[slot*b.rows+row]=iq3::bf16_bits(tree32(s));
   }));});}
#endif
};
template<unsigned K,unsigned R> inline integrated::Launch dense(ownrt::Device&d,const Tokens&a){
 if(!a.rows||a.rows%R||!a.slots||!a.per_token||a.slots%a.per_token||size_t(a.rows)*a.slots>=(size_t(1)<<31)||size_t(a.slots)*K>=(size_t(1)<<31))throw std::invalid_argument("draft batch dense shape");
 extent(d,a.w,size_t(a.rows)*K*2);extent(d,a.x,size_t(a.slots)*K*2);extent(d,a.y,size_t(a.slots)*a.rows*2);
 if(a.tail!=p59::none)extent(d,a.out,size_t(a.slots)*a.rows*2);if(a.tail==p59::merge_add)extent(d,a.other,size_t(a.slots/a.per_token)*a.rows*2);
 if(a.tail!=p59::none&&a.tail!=p59::low&&a.tail!=p59::merge_add)throw std::invalid_argument("draft batch dense tail");
#ifndef OWN_RT_HOST_ONLY
 for(auto id:{a.w,a.x})if(reinterpret_cast<uintptr_t>(d.arena.row(id).pointer)%16)throw std::invalid_argument("draft batch dense alignment");
#endif
 DenseTokens<K,R> op;op.a=a;std::array ids{a.w,a.x,a.y,a.out?a.out:a.y,a.other?a.other:a.x};auto e=d.compute(op,ids,{});return {e,e,1};}
template<unsigned K,unsigned Split> inline integrated::Launch dense_split(ownrt::Device&d,const Tokens&a){
 if(!a.rows||!a.slots||size_t(a.rows)*a.slots>=(size_t(1)<<31)||size_t(a.slots)*K>=(size_t(1)<<31)||(a.tail!=p59::none&&a.tail!=p59::low))throw std::invalid_argument("draft batch split dense shape");
 extent(d,a.w,size_t(a.rows)*K*2);extent(d,a.x,size_t(a.slots)*K*2);extent(d,a.y,size_t(a.slots)*a.rows*2);if(a.tail==p59::low)extent(d,a.out,size_t(a.slots)*a.rows*2);
#ifndef OWN_RT_HOST_ONLY
 for(auto id:{a.w,a.x})if(reinterpret_cast<uintptr_t>(d.arena.row(id).pointer)%16)throw std::invalid_argument("draft batch dense alignment");
#endif
 DenseSplitTokens<K,Split> op;op.a=a;std::array ids{a.w,a.x,a.y,a.out?a.out:a.y,a.x};auto e=d.compute(op,ids,{});return {e,e,1};}
template<unsigned K> inline integrated::Launch gate(ownrt::Device&d,const Tokens&a){
 if(!a.rows||!a.slots||a.tail!=p59::none||size_t(a.rows)*a.slots>=(size_t(1)<<31))throw std::invalid_argument("draft batch gate shape");
 extent(d,a.w,size_t(a.rows)*K*2);extent(d,a.x,size_t(a.slots)*K*2);extent(d,a.y,size_t(a.slots)*a.rows*2);
 GateTokens<K> op;op.a=a;std::array ids{a.w,a.x,a.y,a.y,a.x};auto e=d.compute(op,ids,{});return {e,e,1};}

// mtp36 Elements<mix>: out[t*width+k] = (sum over h<4 of sigmoid(gate[t*4w + h*w + k]) * norm[t*4w + h*w + k]) / 4.
struct MixTokens final:Base {unsigned tokens=0,width=0;
 static void body(const uint16_t* norm,const uint16_t* gate,uint16_t* out,const uint32_t* error,const uint32_t* active,unsigned width,unsigned i){
  if(!*active||*error)return;const unsigned t=i/width,k=i%width;const uint16_t* n0=norm+t*4*width;const uint16_t* g0=gate+t*4*width;float v=0;
  for(unsigned h=0;h<4;++h)v=v+ng::sigmoid(widen(g0[h*width+k]))*widen(n0[h*width+k]);v=v/4.f;out[i]=iq3::bf16_bits(v);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {for(unsigned i=0;i<tokens*width;++i)body(static_cast<const uint16_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),static_cast<const uint32_t*>(p[3]),static_cast<const uint32_t*>(p[4]),width,i);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&)const override {
  auto n0=static_cast<const uint16_t*>(p[0]);auto g0=static_cast<const uint16_t*>(p[1]);auto out=static_cast<uint16_t*>(p[2]);auto error=static_cast<const uint32_t*>(p[3]);auto active=static_cast<const uint32_t*>(p[4]);const unsigned w=width;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(size_t(tokens)*width)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> i){body(n0,g0,out,error,active,w,unsigned(i[0]));}));});}
#endif
};
inline integrated::Launch mix(ownrt::Device&d,Allocation norm,Allocation gate,Allocation out,Allocation error,Allocation active,unsigned tokens,unsigned width){
 if(!tokens||!width||size_t(tokens)*4*width>=(size_t(1)<<31))throw std::invalid_argument("draft batch mix shape");
 extent(d,norm,size_t(tokens)*4*width*2);extent(d,gate,size_t(tokens)*4*width*2);extent(d,out,size_t(tokens)*width*2);extent(d,error,4);extent(d,active,4);
 MixTokens op;op.tokens=tokens;op.width=width;std::array ids{norm,gate,out,error,active};auto e=d.compute(op,ids,{});return {e,e,1};}
}
