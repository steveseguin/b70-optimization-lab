// CPU-device (OpenCL CPU, GPU blocked by nodri.so) bitwise tests of the OWNRT_DECODE_NEXT2 bodies before any GPU launch,
// on real rows of the model's GGUF:
//  hclow   dense_v2::bf16_split<U,4> vs dense_v2::bf16_multi<1,8> (the engine's large-K kernel): HC low + inject fused
//          (320 + 4 rows, K 10240), router (512 x 2560), a ragged synthetic (37 + 5 rows, K 2600);
//  hcgate  dense_v2::bf16_packed and bf16_multi<2|8,4> vs bf16_multi<4,4> (the engine's small-K kernel): HC up
//          (10240 x 320) and a synthetic (2051 x 96);
//  xxs     dn2::xxs_packed<1|2> and dn2::xxs_rows_tab vs a verbatim replica of iq3block::BlockRowsOperation<4>'s body
//          (blk.30.ffn_gate_exps, 10 routed slots incl. one invalid route and one short row_count);
//  sgrid   dn2::decode8_tab<IQ3_S|IQ2_S> vs kopt::decode8 for every 8-column chunk of real expert rows.
#include <sycl/sycl.hpp>
#include "stage2/packet6-kopt/dense_v2.hpp"
#include "stage2/packet194-expert-diet-engine/dn2_kernels.hpp"
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <random>
#include <unistd.h>
#include <vector>
using iq3::Type;
static const char* F1="/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf";
static std::vector<uint8_t> rd(size_t off,size_t n){std::vector<uint8_t> v(n);int fd=::open(F1,O_RDONLY);if(fd<0||::pread(fd,v.data(),n,off_t(off))!=ssize_t(n)){std::perror("read");std::exit(1);}::close(fd);return v;}
static int fails=0;
static void report(const char* what,const float* got,const float* want,size_t n){
 size_t bad=0;for(size_t i=0;i<n;++i)bad+=std::memcmp(got+i,want+i,4)!=0;
 std::printf("  %-58s outputs %7zu mismatches %zu %s\n",what,n,bad,bad?"FAIL":"ok");fails+=bad!=0;
}
template<class T> T* dev(sycl::queue& q,const std::vector<T>& h){T* p=sycl::malloc_device<T>(h.size(),q);q.memcpy(p,h.data(),h.size()*sizeof(T)).wait();return p;}
template<class T> std::vector<T> host(sycl::queue& q,const T* p,size_t n){std::vector<T> h(n);q.memcpy(h.data(),p,n*sizeof(T)).wait();return h;}
// ---- BF16 ----
struct MatH {std::vector<uint8_t> w;uint32_t rows,k;};
static void bf16_case(sycl::queue& q,const char* name,const std::vector<MatH>& mats,bool small){
 const uint32_t k=mats[0].k;std::mt19937 g(k);std::normal_distribution<float> nd(0,1);std::vector<float> xh(k);for(auto& v:xh)v=nd(g);
 float* x=dev(q,xh);std::vector<uint8_t*> w;std::vector<float*> yr,yn;uint32_t total=0;
 for(auto& m:mats){w.push_back(dev(q,m.w));std::vector<float> s(m.rows+16,-777.f);yr.push_back(dev(q,s));yn.push_back(dev(q,s));total+=m.rows;}
 const unsigned count=unsigned(mats.size());
 auto mk=[&](const std::vector<float*>& y,unsigned R,bool rowunits){std::array<iq3::kopt::dense_v2::Mat,4> m{};uint32_t s=0;
  for(unsigned j=0;j<count;++j){m[j]={w[j],x,y[j],mats[j].rows,mats[j].k,mats[j].k*2,s};s+=rowunits?mats[j].rows:(mats[j].rows+R-1)/R;}return std::make_pair(m,s);};
 using namespace iq3::kopt;
 // reference
 {auto [m,subs]=mk(yr,small?4:1,false);const size_t global=(size_t(subs)*32+127)/128*128;
  if(small)q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{dense_v2::bf16_multi<4,4>(m,count,it);}).wait();
  else q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{dense_v2::bf16_multi<1,8>(m,count,it);}).wait();}
 auto check=[&](const char* var){char nm[160];
  for(unsigned j=0;j<count;++j){auto a=host(q,yn[j],mats[j].rows+16),b=host(q,yr[j],mats[j].rows+16);std::snprintf(nm,sizeof nm,"%s %s mat%u (%ux%u)",name,var,j,mats[j].rows,mats[j].k);report(nm,a.data(),b.data(),a.size());
   std::vector<float> s(mats[j].rows+16,-777.f);q.memcpy(yn[j],s.data(),s.size()*4).wait();}};
 if(!small){
  auto [m,total_rows]=mk(yn,1,true);constexpr unsigned WGR=4;const size_t global=size_t((total_rows+WGR-1)/WGR)*WGR*32;
  q.parallel_for(sycl::nd_range<1>(global,WGR*32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(16)]]{float* xch=*sycl::ext::oneapi::group_local_memory_for_overwrite<float[WGR]>(it.get_group());dense_v2::bf16_split<8,WGR>(m,count,it,xch);}).wait();check("split U8");
  q.parallel_for(sycl::nd_range<1>(global,WGR*32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(16)]]{float* xch=*sycl::ext::oneapi::group_local_memory_for_overwrite<float[WGR]>(it.get_group());dense_v2::bf16_split<10,WGR>(m,count,it,xch);}).wait();check("split U10");
  q.parallel_for(sycl::nd_range<1>(global,WGR*32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(16)]]{float* xch=*sycl::ext::oneapi::group_local_memory_for_overwrite<float[WGR]>(it.get_group());dense_v2::bf16_split<4,WGR>(m,count,it,xch);}).wait();check("split U4");
  q.parallel_for(sycl::nd_range<1>(global,WGR*32),dense_v2::SplitLazy<20,WGR,256>{m,count}).wait();check("split lazy U20");
  q.parallel_for(sycl::nd_range<1>(global,WGR*32),dense_v2::SplitLazy<40,WGR,256>{m,count}).wait();check("split lazy U40");
 } else {
  {auto [m,total_rows]=mk(yn,1,true);const size_t global=size_t((total_rows+7)/8)*64;
   q.parallel_for(sycl::nd_range<1>(global,64),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(16)]]{dense_v2::bf16_packed(m,count,it);}).wait();check("packed");}
  {auto [m,subs]=mk(yn,2,false);const size_t global=(size_t(subs)*32+127)/128*128;
   q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{dense_v2::bf16_multi<2,4>(m,count,it);}).wait();check("R2");}
  {auto [m,subs]=mk(yn,8,false);const size_t global=(size_t(subs)*32+127)/128*128;
   q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{dense_v2::bf16_multi<8,4>(m,count,it);}).wait();check("R8");}
 }
 for(auto p:w)sycl::free(p,q);for(auto p:yr)sycl::free(p,q);for(auto p:yn)sycl::free(p,q);sycl::free(x,q);
}
static std::vector<uint8_t> synth_bf16(uint32_t rows,uint32_t k,unsigned seed){std::mt19937 g(seed);std::normal_distribution<float> nd(0,0.05f);std::vector<uint8_t> v(size_t(rows)*k*2);
 for(size_t i=0;i<size_t(rows)*k;++i){float f=nd(g);uint32_t b;std::memcpy(&b,&f,4);uint16_t h=uint16_t(b>>16);std::memcpy(&v[2*i],&h,2);}return v;}
// ---- IQ3_XXS: verbatim replica of iq3block::BlockRowsOperation<4> (block.hpp) on the XxsView ----
inline float ref_element_words(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const uint32_t index=(uint32_t(reinterpret_cast<const uint16_t*>(b+2+group*8)[lane/8])>>(8*((lane/4)%2)))&255;
 const auto mag=(iq3::iq3_grid[index]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
}
static void ref_rows(sycl::queue& q,dn2::XxsView b){
 constexpr unsigned R=4;const size_t blocks=(b.rows+R-1)/R;
 q.parallel_for(sycl::nd_range<1>(blocks*b.count*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
   const auto r=b.routes[slot];const bool valid=iq3::valid_route(r,b.experts,uint32_t(b.rows),uint32_t(b.rows));
   const float* x=b.x+size_t(slot)*b.columns;float acc[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i)acc[i]=0;
   const uint8_t* rows[R];bool live[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i){const size_t row=first+i;live[i]=valid&&row<b.rows&&row<r.row_count;rows[i]=live[i]?b.w+(size_t(r.expert_id)*b.rows+r.row_begin+row)*b.row_bytes:b.w;}
   const uint32_t nblocks=uint32_t(b.columns/256);
   for(uint32_t block=0;block<nblocks;++block){
    #pragma unroll
    for(unsigned i=0;i<R;++i){if(!live[i])continue;
     const auto*packed=rows[i]+block*98u;const float d=iq3::half(iq3::u16(packed));
     #pragma unroll
     for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;const float weight=ref_element_words(packed,d,group,lane);const float product=weight*x[k];acc[i]=acc[i]+product;}}
   }
   #pragma unroll
   for(unsigned i=0;i<R;++i){float sum=acc[i];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<b.rows)b.y[size_t(slot)*b.rows+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&first==0&&b.status)b.status[slot]=!valid;
 }).wait();
}
static void xxs_case(sycl::queue& q){
 const uint32_t rows=640,cols=2560,rb=980,experts_used=8,slots=10;const size_t off=34174327936ull;
 // experts 0..7 of the tensor stand in as a compact 8-expert tensor (row layout identical); routes into them.
 auto wh=rd(off,size_t(experts_used)*rows*rb);
 std::vector<iq3::Route> rt(slots);std::mt19937 g(7);
 for(uint32_t s=0;s<slots;++s)rt[s]={uint32_t(g()%experts_used),0,rows};
 rt[3]={experts_used+5,0,rows}; // invalid expert id: NaN rows, status 1
 rt[6].row_count=301;           // short route: rows >= 301 NaN
 std::vector<float> xh(size_t(slots)*cols);std::normal_distribution<float> nd(0,1);for(auto& v:xh)v=nd(g);xh[17]=-0.f;
 uint8_t* w=dev(q,wh);float* x=dev(q,xh);iq3::Route* r=dev(q,rt);
 std::vector<float> sent(size_t(slots)*rows+32,-777.f);std::vector<uint32_t> ss(slots,77);
 float* yr=dev(q,sent);float* yn=dev(q,sent);uint32_t* sr=dev(q,ss);uint32_t* sn=dev(q,ss);
 dn2::XxsView vr{w,x,yr,r,sr,rows,cols,rb,slots,experts_used},vn{w,x,yn,r,sn,rows,cols,rb,slots,experts_used};
 ref_rows(q,vr);auto want=host(q,yr,sent.size());auto swant=host(q,sr,slots);
 auto run=[&](int mode){q.memcpy(yn,sent.data(),sent.size()*4).wait();q.memcpy(sn,ss.data(),slots*4).wait();constexpr unsigned WGSG=4;
  if(mode==3){const uint32_t blocks=(rows+3)/4,total=blocks*slots,groups=(total+WGSG-1)/WGSG;
   q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::xxs_rows_tab<WGSG>(vn,it);}).wait();}
  else {const uint32_t blocks=(rows+1)/2,total=blocks*slots,groups=(total+WGSG-1)/WGSG;
   if(mode==1)q.parallel_for(sycl::nd_range<1>(size_t(groups)*16*WGSG,16*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(16)]]{dn2::xxs_packed<1,WGSG>(vn,it);}).wait();
   else q.parallel_for(sycl::nd_range<1>(size_t(groups)*16*WGSG,16*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(16)]]{dn2::xxs_packed<2,WGSG>(vn,it);}).wait();}
  auto got=host(q,yn,sent.size());auto sgot=host(q,sn,slots);char nm[96];std::snprintf(nm,sizeof nm,"IQ3_XXS blk.30 gate xxs mode %d (10 slots, 1 invalid, 1 short)",mode);
  report(nm,got.data(),want.data(),got.size());const bool st=std::memcmp(sgot.data(),swant.data(),slots*4)==0;std::printf("    status %s (invalid slot status %u)\n",st?"ok":"FAIL",sgot[3]);fails+=!st;};
 run(1);run(2);run(3);
 size_t nans=0;for(size_t i=0;i<size_t(slots)*rows;++i)nans+=want[i]!=want[i];std::printf("    reference NaN outputs %zu (expected %u)\n",nans,rows+(rows-301));
 sycl::free(w,q);sycl::free(x,q);sycl::free(r,q);sycl::free(yr,q);sycl::free(yn,q);sycl::free(sr,q);sycl::free(sn,q);
}
template<Type T,bool G=false> static void sgrid_case(sycl::queue& q,const char* name,size_t off,uint32_t rb){
 const uint32_t rows=64,k=2560;auto wh=rd(off+size_t(rb)*640*3,size_t(rows)*rb); // expert 3, rows 0..63
 uint8_t* w=dev(q,wh);const size_t n=size_t(rows)*k;float* a=sycl::malloc_device<float>(n,q);float* b=sycl::malloc_device<float>(n,q);
 q.parallel_for(sycl::nd_range<1>(size_t(rows)*(k/8),128),[=](sycl::nd_item<1> it){
  const uint32_t* tab=G?(T==Type::IQ2_S?reinterpret_cast<const uint32_t*>(iq3::iq2_s_grid):iq3::iq3_s_grid):dn2::grid_tab<T,128>(it);const size_t id=it.get_global_linear_id();const uint32_t row=uint32_t(id/(k/8)),c=uint32_t(id%(k/8))*8;
  float v[8],u[8];dn2::decode8_tab<T>(w+size_t(row)*rb,c,v,tab);iq3::kopt::decode8<T>(w+size_t(row)*rb,c,u);
  for(unsigned j=0;j<8;++j){a[size_t(row)*k+c+j]=v[j];b[size_t(row)*k+c+j]=u[j];}}).wait();
 auto ga=host(q,a,n),gb=host(q,b,n);char nm[96];std::snprintf(nm,sizeof nm,"%s decode8_tab vs decode8 (64 rows x 2560)",name);report(nm,ga.data(),gb.data(),n);
 sycl::free(w,q);sycl::free(a,q);sycl::free(b,q);
}

// ---- IQ3_S / IQ2_S: verbatim replica of kopt MultiplyBlockRows<4>::run<T,32> (kernels.cpp) on the SView ----
template<Type T> static void ref_block_rows(sycl::queue& q,dn2::SView d){
 constexpr unsigned R=4,Subgroups=4,SG=32;const size_t blocks=(d.span+R-1)/R,total=blocks*d.count,groups=(total+Subgroups-1)/Subgroups;
 q.parallel_for(sycl::nd_range<1>(groups*SG*Subgroups,SG*Subgroups),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(SG)]]{
  using namespace iq3;using namespace iq3::kopt;
  auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
  const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
  const size_t slot=logical/blocks,first=(logical%blocks)*R;
  Route r{0,0,uint32_t(d.rows)};if(d.routed)r=d.routes[slot];
  const bool valid=valid_route(r,d.experts,d.rows,d.span);
  if(d.routed&&first==0&&lane==0)d.status[slot]=valid?0:1;
  const float* x=d.x+slot*d.k;const uint8_t* w=d.w;
  float acc[R];const uint8_t* rows[R];bool live[R];
  #pragma unroll
  for(unsigned i=0;i<R;++i){acc[i]=0;const size_t row=first+i;live[i]=valid&&row<d.span&&row<r.row_count;
    rows[i]=live[i]?w+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb:w;}
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
  #pragma unroll
  for(unsigned i=0;i<R;++i) {
    float sum=acc[i];
    for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<d.span)d.y[slot*d.span+row]=valid&&row<r.row_count?sum:bits_float(0x7fc00000);
  }
 }).wait();
}
template<Type T> static void spacked_case(sycl::queue& q,const char* name,size_t off,uint32_t rb){
 const uint32_t rows=640,k=2560,experts_used=8,slots=10;auto wh=rd(off,size_t(experts_used)*rows*rb);
 std::vector<iq3::Route> rt(slots);std::mt19937 g(11);for(uint32_t s=0;s<slots;++s)rt[s]={uint32_t(g()%experts_used),0,rows};
 rt[2]={experts_used+1,0,rows};rt[7].row_count=333;
 std::vector<float> xh(size_t(slots)*k);std::normal_distribution<float> nd(0,1);for(auto& v:xh)v=nd(g);
 uint8_t* w=dev(q,wh);float* x=dev(q,xh);iq3::Route* r=dev(q,rt);
 std::vector<float> sent(size_t(slots)*rows+32,-777.f);std::vector<uint32_t> ss(slots,77);
 float* yr=dev(q,sent);float* yn=dev(q,sent);uint32_t* sr=dev(q,ss);uint32_t* sn=dev(q,ss);
 dn2::SView vr{w,x,yr,r,sr,rows,rows,k,rb,slots,experts_used,true},vn{w,x,yn,r,sn,rows,rows,k,rb,slots,experts_used,true};
 ref_block_rows<T>(q,vr);auto want=host(q,yr,sent.size());auto swant=host(q,sr,slots);
 auto run=[&](int sgw,bool tab){q.memcpy(yn,sent.data(),sent.size()*4).wait();q.memcpy(sn,ss.data(),slots*4).wait();constexpr unsigned WGSG=4;
  const uint32_t sets=uint32_t(sgw/8),blocks=(rows+sets-1)/sets,total=blocks*slots,groups=(total+WGSG-1)/WGSG;
  if(sgw==16&&!tab)q.parallel_for(sycl::nd_range<1>(size_t(groups)*16*WGSG,16*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(16)]]{dn2::s_packed<T,16,false,WGSG>(vn,it);}).wait();
  if(sgw==16&&tab)q.parallel_for(sycl::nd_range<1>(size_t(groups)*16*WGSG,16*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(16)]]{dn2::s_packed<T,16,true,WGSG>(vn,it);}).wait();
  if(sgw==32&&!tab)q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::s_packed<T,32,false,WGSG>(vn,it);}).wait();
  if(sgw==32&&tab)q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::s_packed<T,32,true,WGSG>(vn,it);}).wait();
  auto got=host(q,yn,sent.size());auto sgot=host(q,sn,slots);char nm[110];std::snprintf(nm,sizeof nm,"%s s_packed SG%d tab %d (10 slots, 1 invalid, 1 short)",name,sgw,int(tab));
  report(nm,got.data(),want.data(),got.size());const bool st=std::memcmp(sgot.data(),swant.data(),slots*4)==0;std::printf("    status %s (invalid slot %u)\n",st?"ok":"FAIL",sgot[2]);fails+=!st;};
 run(16,false);run(16,true);run(32,false);run(32,true);
 size_t nans=0;for(size_t i=0;i<size_t(slots)*rows;++i)nans+=want[i]!=want[i];std::printf("    reference NaN outputs %zu (expected %u)\n",nans,rows+(rows-333));
 sycl::free(w,q);sycl::free(x,q);sycl::free(r,q);sycl::free(yr,q);sycl::free(yn,q);sycl::free(sr,q);sycl::free(sn,q);
}
static void xxs32_case(sycl::queue& q){
 const uint32_t rows=640,cols=2560,rb=980,experts_used=8,slots=10;auto wh=rd(34174327936ull,size_t(experts_used)*rows*rb);
 std::vector<iq3::Route> rt(slots);std::mt19937 g(5);for(uint32_t s=0;s<slots;++s)rt[s]={uint32_t(g()%experts_used),0,rows};rt[4]={99,0,rows};rt[8].row_count=77;
 std::vector<float> xh(size_t(slots)*cols);std::normal_distribution<float> nd(0,1);for(auto& v:xh)v=nd(g);
 uint8_t* w=dev(q,wh);float* x=dev(q,xh);iq3::Route* r=dev(q,rt);std::vector<float> sent(size_t(slots)*rows+32,-777.f);std::vector<uint32_t> ss(slots,77);
 float* yr=dev(q,sent);float* yn=dev(q,sent);uint32_t* sr=dev(q,ss);uint32_t* sn=dev(q,ss);
 dn2::XxsView vr{w,x,yr,r,sr,rows,cols,rb,slots,experts_used},vn{w,x,yn,r,sn,rows,cols,rb,slots,experts_used};
 ref_rows(q,vr);auto want=host(q,yr,sent.size());auto swant=host(q,sr,slots);
 for(int mode:{1,2}){q.memcpy(yn,sent.data(),sent.size()*4).wait();q.memcpy(sn,ss.data(),slots*4).wait();constexpr unsigned WGSG=4;
  const uint32_t blocks=(rows+3)/4,total=blocks*slots,groups=(total+WGSG-1)/WGSG;
  if(mode==1)q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::xxs_packed<1,WGSG,32>(vn,it);}).wait();
  else q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::xxs_packed<2,WGSG,32>(vn,it);}).wait();
  auto got=host(q,yn,sent.size());auto sgot=host(q,sn,slots);char nm[96];std::snprintf(nm,sizeof nm,"IQ3_XXS blk.30 gate xxs packed SG32 mode %d",mode);
  report(nm,got.data(),want.data(),got.size());const bool st=std::memcmp(sgot.data(),swant.data(),slots*4)==0;std::printf("    status %s\n",st?"ok":"FAIL");fails+=!st;}
 // xxspair: gate (blk.30 gate) + up (blk.30 up) in one launch vs the reference run on each matrix
 {auto uh=rd(34498951296ull,size_t(experts_used)*rows*rb);uint8_t* wu=dev(q,uh);
  float* yur=dev(q,sent);float* yun=dev(q,sent);uint32_t* sur=dev(q,ss);uint32_t* sun=dev(q,ss);
  dn2::XxsView vur{wu,x,yur,r,sur,rows,cols,rb,slots,experts_used};ref_rows(q,vur);auto wantu=host(q,yur,sent.size());auto swantu=host(q,sur,slots);
  q.memcpy(yn,sent.data(),sent.size()*4).wait();q.memcpy(sn,ss.data(),slots*4).wait();
  dn2::XxsView vg{w,x,yn,r,sn,rows,cols,rb,slots,experts_used},vu{wu,x,yun,r,sun,rows,cols,rb,slots,experts_used};
  constexpr unsigned WGSG=4;const uint32_t total=2*((rows+3)/4)*slots,groups=(total+WGSG-1)/WGSG;
  q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::xxs_packed_pair<2,WGSG,32>(vg,vu,it);}).wait();
  auto gg=host(q,yn,sent.size()),gu=host(q,yun,sent.size());auto sg_=host(q,sn,slots),su=host(q,sun,slots);
  report("IQ3_XXS blk.30 xxspair gate outputs",gg.data(),want.data(),gg.size());report("IQ3_XXS blk.30 xxspair up outputs",gu.data(),wantu.data(),gu.size());
  const bool st=!std::memcmp(sg_.data(),swant.data(),slots*4)&&!std::memcmp(su.data(),swantu.data(),slots*4);std::printf("    pair statuses %s\n",st?"ok":"FAIL");fails+=!st;
  sycl::free(wu,q);sycl::free(yur,q);sycl::free(yun,q);sycl::free(sur,q);sycl::free(sun,q);}
 sycl::free(w,q);sycl::free(x,q);sycl::free(r,q);sycl::free(yr,q);sycl::free(yn,q);sycl::free(sr,q);sycl::free(sn,q);
}
int main(int argc,char** argv){
 const bool only_new=argc>1&&std::string(argv[1])=="new";
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 if(only_new){sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  if(argc>2&&std::string(argv[2])=="g"){sgrid_case<Type::IQ2_S,true>(q,"IQ2_S blk.23 gate global split",26050796800ull,820);sgrid_case<Type::IQ3_S,true>(q,"IQ3_S blk.25 gate global",28224668800ull,1100);std::printf(fails?"FAIL (%d)\n":"PASS\n",fails);return fails?1:0;}
  if(argc>2){xxs32_case(q);std::printf(fails?"FAIL (%d)\n":"PASS\n",fails);return fails?1:0;}
  {MatH low{rd(34820999296ull,6553600),320,10240},inj{rd(34827552896ull,81920),4,10240};bf16_case(q,"HC low+inject blk.30",{low,inj},false);}
  {MatH a{synth_bf16(37,2600,1),37,2600},b{synth_bf16(5,2600,2),5,2600};bf16_case(q,"synthetic ragged K 2600",{a,b},false);}
  spacked_case<Type::IQ3_S>(q,"IQ3_S blk.25 gate",28224668800ull,1100);spacked_case<Type::IQ2_S>(q,"IQ2_S blk.23 gate",26050796800ull,820);xxs32_case(q);
  std::printf(fails?"FAIL (%d)\n":"PASS\n",fails);return fails?1:0;}
 {MatH low{rd(34820999296ull,6553600),320,10240},inj{rd(34827552896ull,81920),4,10240};bf16_case(q,"HC low+inject blk.30",{low,inj},false);}
 {MatH router{rd(34495454336ull,2621440),512,2560};bf16_case(q,"router blk.30",{router},false);}
 {MatH a{synth_bf16(37,2600,1),37,2600},b{synth_bf16(5,2600,2),5,2600};bf16_case(q,"synthetic ragged K 2600",{a,b},false);}
 {MatH up{rd(34827675776ull,6553600),10240,320};bf16_case(q,"HC gate blk.30",{up},true);}
 {MatH s{synth_bf16(2051,96,3),2051,96};bf16_case(q,"synthetic small K 96",{s},true);}
 xxs_case(q);
 sgrid_case<Type::IQ3_S>(q,"IQ3_S blk.25 gate",28224668800ull,1100);
 sgrid_case<Type::IQ2_S>(q,"IQ2_S blk.23 gate",26050796800ull,820);
 std::printf(fails?"FAIL (%d)\n":"PASS\n",fails);return fails?1:0;
}
