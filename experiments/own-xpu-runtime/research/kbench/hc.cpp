// Kernel microbenchmark: BF16-weight GEMV with F32 activations at the HC shapes. Variants must be bitwise equal to the
// engine's kopt raw path (v0): lane l owns k=l*8+256*i (SG32), product then add per element in order, adjacent-pair tree.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
static inline float bf(uint16_t v){uint32_t b=uint32_t(v)<<16;if((b&0x7fffffff)>0x7f800000)b|=0x400000;float f;std::memcpy(&f,&b,4);return f;}
template<int V,int RowsPerSg> struct K;
// V0: engine kopt Multiply raw path (4 subgroups per work-group, one row each).
template<int RowsPerSg>
sycl::event run_pipelined(sycl::queue& q,const uint16_t* w,const float* x,float* y,int rows,int k){
  constexpr int SG=32,SGS=4;const int per_wg=SGS*RowsPerSg;const size_t groups=(rows+per_wg-1)/per_wg;
  return q.parallel_for<K<1,RowsPerSg>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const int lane=sg.get_local_linear_id();const int row=(it.get_group_linear_id()*SGS+sg.get_group_linear_id());
    if(row>=rows)return;const uint16_t* wr=w+size_t(row)*k;float acc=0;
    int base=lane*8;sycl::vec<uint16_t,8> cur{};if(base<k)cur=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(wr+base);
    for(;base<k;base+=SG*8){
      sycl::vec<uint16_t,8> next{};if(base+SG*8<k)next=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(wr+base+SG*8);
      for(int j=0;j<8;++j){float value=bf(cur[j]);float product=value*x[base+j];acc=acc+product;}
      cur=next;}
    float sum=acc;for(int width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
    if(lane==0)y[row]=sum;
  });
}
// Engine-faithful replica of kopt Multiply's raw BF16 path: 4 subgroups per work-group, a local accessor, the
// work-group barrier that quantized staging needs, and the alignment-checked vector load. BARRIER=false drops only the
// barrier.
template<bool BARRIER>
sycl::event run_engine(sycl::queue& q,const uint16_t* w,const float* x,float* y,int rows,int k){
  constexpr int SG=32,SGS=4;const size_t groups=(rows+SGS-1)/SGS;
  return q.submit([&](sycl::handler& h){sycl::local_accessor<uint8_t,1> storage(16*SGS,h);
   h.parallel_for<K<10+BARRIER,1>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const int lane=sg.get_local_linear_id();const int row=it.get_group_linear_id()*SGS+sg.get_group_linear_id();
    const bool active=row<rows;const uint16_t* src=w+size_t(active?row:0)*k;
    if constexpr(BARRIER)it.barrier(sycl::access::fence_space::local_space);
    float acc=0;
    if(active)for(int base=lane*8;base<k;base+=SG*8){float values[8],wide[8];
      if(base+8<=k&&reinterpret_cast<uintptr_t>(src+base)%16==0&&reinterpret_cast<uintptr_t>(reinterpret_cast<const uint16_t*>(x)+base)%16==0){
        for(int j=0;j<8;++j)wide[j]=x[base+j];auto wv=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(src+base);for(int j=0;j<8;++j)values[j]=bf(wv[j]);}
      else for(int j=0;j<8&&base+j<k;++j){values[j]=bf(src[base+j]);wide[j]=x[base+j];}
      for(int j=0;j<8&&base+j<k;++j){float product=values[j]*wide[j];acc=acc+product;}}
    for(int width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,acc,(lane+width)%SG);if(lane%(2*width)==0)acc=acc+rhs;}
    if(lane==0&&active)y[row]=acc;});});
}
template<int V,int RowsPerSg>
sycl::event run(sycl::queue& q,const uint16_t* w,const float* x,float* y,int rows,int k){
  constexpr int SG=32,SGS=4;const int per_wg=SGS*RowsPerSg;const size_t groups=(rows+per_wg-1)/per_wg;
  return q.parallel_for<K<V,RowsPerSg>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const int lane=sg.get_local_linear_id();const int row0=(it.get_group_linear_id()*SGS+sg.get_group_linear_id())*RowsPerSg;
    float acc[RowsPerSg];for(int r=0;r<RowsPerSg;++r)acc[r]=0;
    for(int base=lane*8;base<k;base+=SG*8){
      float in[8];for(int j=0;j<8;++j)in[j]=x[base+j];
      #pragma unroll
      for(int r=0;r<RowsPerSg;++r){int row=row0+r;if(row>=rows)break;
        auto wv=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(w+size_t(row)*k+base);
        for(int j=0;j<8;++j){float value=bf(wv[j]);float product=value*in[j];acc[r]=acc[r]+product;}}
    }
    for(int r=0;r<RowsPerSg;++r){float sum=acc[r];for(int width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
      if(lane==0&&row0+r<rows)y[row0+r]=sum;}
  });
}
int main(int argc,char** argv){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("%s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  struct Shape{const char* name;int rows,k;};
  for(Shape s:{Shape{"hc.low 320x10240",320,10240},Shape{"hc.inject 4x10240",4,10240},Shape{"hc.gate 10240x320",10240,320},Shape{"router 512x2560",512,2560},Shape{"low+inject 324x10240",324,10240}}){
    std::mt19937 g(1);std::vector<uint16_t> hw(size_t(s.rows)*s.k);std::vector<float> hx(s.k);
    for(auto& v:hw){float f=std::uniform_real_distribution<float>(-0.05f,0.05f)(g);uint32_t b;std::memcpy(&b,&f,4);v=uint16_t(b>>16);}
    for(auto& v:hx)v=std::uniform_real_distribution<float>(-2,2)(g);
    auto* w=sycl::malloc_device<uint16_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(s.k,q);auto* y=sycl::malloc_device<float>(s.rows,q);
    q.memcpy(w,hw.data(),hw.size()*2).wait();q.memcpy(x,hx.data(),s.k*4).wait();
    std::vector<float> ref(s.rows),out(s.rows);
    auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  auto time=[&](auto fn,const char* label){for(int i=0;i<20;++i)fn().wait();std::vector<double> t,tc;
      for(int i=0;i<200;++i){auto e=fn();e.wait();tc.push_back(0);t.push_back((e.template get_profiling_info<sycl::info::event_profiling::command_end>()-e.template get_profiling_info<sycl::info::event_profiling::command_start>())/1000.0);}
      std::vector<double> cold;for(int i=0;i<60;++i){q.fill(junk,float(i),64*1024*1024).wait();auto e=fn();e.wait();cold.push_back((e.template get_profiling_info<sycl::info::event_profiling::command_end>()-e.template get_profiling_info<sycl::info::event_profiling::command_start>())/1000.0);}
      std::sort(t.begin(),t.end());std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,s.rows*4).wait();bool same=std::memcmp(out.data(),ref.data(),s.rows*4)==0;
      std::printf("  %-28s warm %8.2f us  cold %8.2f us  %s\n",label,t[t.size()/2],cold[cold.size()/2],same?"bitwise-equal":"DIFFERS");};
    std::printf("%s (%.1f MB weights)\n",s.name,hw.size()*2/1e6);
    run<0,1>(q,w,x,y,s.rows,s.k).wait();q.memcpy(ref.data(),y,s.rows*4).wait();
    time([&]{return run<0,1>(q,w,x,y,s.rows,s.k);},"v0 1 row/subgroup");
    time([&]{return run_engine<true>(q,w,x,y,s.rows,s.k);},"engine replica (barrier)");
    time([&]{return run_engine<false>(q,w,x,y,s.rows,s.k);},"engine replica, no barrier");
    time([&]{return run<0,2>(q,w,x,y,s.rows,s.k);},"2 rows/subgroup");
    time([&]{return run<0,4>(q,w,x,y,s.rows,s.k);},"4 rows/subgroup");
    time([&]{return run<0,8>(q,w,x,y,s.rows,s.k);},"8 rows/subgroup");
    time([&]{return run_pipelined<1>(q,w,x,y,s.rows,s.k);},"pipelined weight load");
    sycl::free(w,q);sycl::free(x,q);sycl::free(y,q);
  }
}
