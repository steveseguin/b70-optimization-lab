// CPU-device (OpenCL CPU, GPU blocked by nodri.so) bitwise tests of the final OWNRT_DECODE_NEXT2 bodies (the engine's
// headers, compiled here unchanged) against the kernels they replace, on real rows of the model's GGUF:
//  xxs        dn2::xxs_packed<4> vs a verbatim replica of iq3block::BlockRowsOperation<4> (blk.30 gate and up, 10 slots
//             incl. an invalid route and a short row_count; statuses);
//  hcgate     dense_v2::bf16_multi<2,4> vs bf16_multi<4,4> (HC gate blk.30, 10240 x 320; synthetic 2051 x 96);
//  bf16split  dense_v2::bf16_split<10,4> vs bf16_multi<1,8> (router+shared-gate-like pair 512+1 x 2560, GDN a+b
//             48+48 x 2560, synthetic 37+5 x 2600);
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
  q.parallel_for(sycl::nd_range<1>(global,WGR*32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(16)]]{float* xch=*sycl::ext::oneapi::group_local_memory_for_overwrite<float[WGR]>(it.get_group());dense_v2::bf16_split<10,WGR>(m,count,it,xch);}).wait();check("bf16_split<10,4>");
 } else {
  auto [m,subs]=mk(yn,2,false);const size_t global=(size_t(subs)*32+127)/128*128;
  q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{dense_v2::bf16_multi<2,4>(m,count,it);}).wait();check("bf16_multi<2,4>");
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
static void xxs_case(sycl::queue& q,const char* name,size_t off){
 const uint32_t rows=640,cols=2560,rb=980,experts_used=8,slots=10;
 auto wh=rd(off,size_t(experts_used)*rows*rb);
 std::vector<iq3::Route> rt(slots);std::mt19937 g(7);
 for(uint32_t s=0;s<slots;++s)rt[s]={uint32_t(g()%experts_used),0,rows};
 rt[3]={experts_used+5,0,rows};rt[6].row_count=301;
 std::vector<float> xh(size_t(slots)*cols);std::normal_distribution<float> nd(0,1);for(auto& v:xh)v=nd(g);xh[17]=-0.f;
 uint8_t* w=dev(q,wh);float* x=dev(q,xh);iq3::Route* r=dev(q,rt);
 std::vector<float> sent(size_t(slots)*rows+32,-777.f);std::vector<uint32_t> ss(slots,77);
 float* yr=dev(q,sent);float* yn=dev(q,sent);uint32_t* sr=dev(q,ss);uint32_t* sn=dev(q,ss);
 dn2::XxsView vr{w,x,yr,r,sr,rows,cols,rb,slots,experts_used},vn{w,x,yn,r,sn,rows,cols,rb,slots,experts_used};
 ref_rows(q,vr);auto want=host(q,yr,sent.size());auto swant=host(q,sr,slots);
 constexpr unsigned WGSG=4;const uint32_t total=((rows+3)/4)*slots,groups=(total+WGSG-1)/WGSG;
 q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::xxs_packed<WGSG>(vn,it);}).wait();
 auto got=host(q,yn,sent.size());auto sgot=host(q,sn,slots);char nm[96];std::snprintf(nm,sizeof nm,"%s xxs_packed<4> (10 slots, 1 invalid, 1 short)",name);
 report(nm,got.data(),want.data(),got.size());const bool st=std::memcmp(sgot.data(),swant.data(),slots*4)==0;std::printf("    status %s (invalid slot %u)\n",st?"ok":"FAIL",sgot[3]);fails+=!st;
 size_t nans=0;for(size_t i=0;i<size_t(slots)*rows;++i)nans+=want[i]!=want[i];std::printf("    reference NaN outputs %zu (expected %u)\n",nans,rows+(rows-301));
 sycl::free(w,q);sycl::free(x,q);sycl::free(r,q);sycl::free(yr,q);sycl::free(yn,q);sycl::free(sr,q);sycl::free(sn,q);
}
int main(){
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 xxs_case(q,"IQ3_XXS blk.30 gate",34174327936ull);xxs_case(q,"IQ3_XXS blk.30 up",34498951296ull);
 {MatH up{rd(34827675776ull,6553600),10240,320};bf16_case(q,"HC gate blk.30",{up},true);}
 {MatH s{synth_bf16(2051,96,3),2051,96};bf16_case(q,"synthetic small K 96",{s},true);}
 {MatH router{rd(34495454336ull,2621440),512,2560},sg{rd(34498075776ull,5120),1,2560};bf16_case(q,"router+shared gate blk.30",{router,sg},false);}
 {MatH ga{rd(34847459648ull,245760),48,2560},gb{rd(34847705408ull,245760),48,2560};bf16_case(q,"GDN a+b blk.30",{ga,gb},false);}
 {MatH a{synth_bf16(37,2600,1),37,2600},b{synth_bf16(5,2600,2),5,2600};bf16_case(q,"synthetic K 2600",{a,b},false);}
 std::printf(fails?"FAIL (%d)\n":"PASS\n",fails);return fails?1:0;
}
