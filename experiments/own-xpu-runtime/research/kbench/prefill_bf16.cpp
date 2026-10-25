// Prefill BF16 dense GEMV with M token rows (F32 activations): the engine's per-output arithmetic is fixed -
// lane l owns columns l*8+256*i in order, product then add, then the adjacent-pair 32-lane tree. Variants only change
// how many (row, token) outputs one subgroup carries: R weight rows x T tokens, each weight chunk decoded once per
// subgroup and each activation chunk loaded once per subgroup. All variants must be bitwise equal to R=1,T=1.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
template<int V> struct KK;
template<int V,int R,int T>
sycl::event run(sycl::queue& q,const uint16_t* w,const float* x,float* y,int rows,int k,int m){
  constexpr int SG=32,SGS=4;const int rtiles=(rows+R-1)/R,ttiles=(m+T-1)/T;const size_t total=size_t(rtiles)*ttiles,groups=(total+SGS-1)/SGS;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id()*SGS+sg.get_group_linear_id();
    if(logical>=total)return;const int row0=int(logical/ttiles)*R,tok0=int(logical%ttiles)*T;
    float acc[R][T];
    #pragma unroll
    for(int r=0;r<R;++r)
      #pragma unroll
      for(int t=0;t<T;++t)acc[r][t]=0.f;
    const uint16_t* src[R];
    #pragma unroll
    for(int r=0;r<R;++r)src[r]=w+size_t(row0+r<rows?row0+r:row0)*k;
    for(uint32_t base=lane*8u;base+8u<=uint32_t(k);base+=SG*8u){
      float wv[R][8];
      #pragma unroll
      for(int r=0;r<R;++r){auto v=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(src[r]+base);
        #pragma unroll
        for(int j=0;j<8;++j)wv[r][j]=sycl::bit_cast<float>(uint32_t(v[j])<<16);}
      #pragma unroll
      for(int t=0;t<T;++t){const float* xt=x+size_t(tok0+t<m?tok0+t:tok0)*k+base;float xv[8];
        #pragma unroll
        for(int j=0;j<8;++j)xv[j]=xt[j];
        #pragma unroll
        for(int r=0;r<R;++r)
          #pragma unroll
          for(int j=0;j<8;++j){float product=wv[r][j]*xv[j];acc[r][t]=acc[r][t]+product;}}
    }
    #pragma unroll
    for(int r=0;r<R;++r)
      #pragma unroll
      for(int t=0;t<T;++t){float a=acc[r][t];for(int width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,a,(lane+width)%SG);if(lane%(2*width)==0)a=a+rhs;}
        if(lane==0&&row0+r<rows&&tok0+t<m)y[size_t(tok0+t)*rows+row0+r]=a;}
  });
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  struct Shape{const char* name;int rows,k;};
  for(Shape s:{Shape{"hc.low 320x10240",320,10240},Shape{"hc.gate 10240x320",10240,320},Shape{"router 512x2560",512,2560}}){
    const int m=16;std::mt19937 g(1);std::vector<uint16_t> hw(size_t(s.rows)*s.k);std::vector<float> hx(size_t(m)*s.k);
    for(auto& v:hw){float f=std::uniform_real_distribution<float>(-0.05f,0.05f)(g);uint32_t b;std::memcpy(&b,&f,4);v=uint16_t(b>>16);}
    for(auto& v:hx)v=std::uniform_real_distribution<float>(-2,2)(g);
    auto* w=sycl::malloc_device<uint16_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(size_t(m)*s.rows,q);
    q.memcpy(w,hw.data(),hw.size()*2).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();
    std::vector<float> ref(size_t(m)*s.rows),out(ref.size());run<0,1,1>(q,w,x,y,s.rows,s.k,m).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
    auto time=[&](auto fn,const char* label){for(int i=0;i<5;++i)fn().wait();std::vector<double> cold;
      for(int i=0;i<30;++i){q.fill(junk,float(i),64*1024*1024).wait();auto e=fn();e.wait();cold.push_back((e.template get_profiling_info<sycl::info::event_profiling::command_end>()-e.template get_profiling_info<sycl::info::event_profiling::command_start>())/1000.0);}
      std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,out.size()*4).wait();
      std::printf("  %-22s cold %8.1f us  %s\n",label,cold[cold.size()/2],std::memcmp(out.data(),ref.data(),out.size()*4)?"DIFFERS":"bitwise-equal");};
    std::printf("%s, %d tokens\n",s.name,m);
    time([&]{return run<0,1,1>(q,w,x,y,s.rows,s.k,m);},"R1 T1");
    time([&]{return run<1,1,4>(q,w,x,y,s.rows,s.k,m);},"R1 T4 (engine-like)");
    time([&]{return run<2,1,8>(q,w,x,y,s.rows,s.k,m);},"R1 T8");
    time([&]{return run<3,2,4>(q,w,x,y,s.rows,s.k,m);},"R2 T4");
    time([&]{return run<4,2,8>(q,w,x,y,s.rows,s.k,m);},"R2 T8");
    time([&]{return run<5,4,4>(q,w,x,y,s.rows,s.k,m);},"R4 T4");
    time([&]{return run<6,1,16>(q,w,x,y,s.rows,s.k,m);},"R1 T16");
    sycl::free(w,q);sycl::free(x,q);sycl::free(y,q);
  }
}
