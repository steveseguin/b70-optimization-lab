// Route (512 experts, top 10, one row) microbenchmark: exact replica of adapter.cpp RouteFast (softmax, ten
// work-group arg-max rounds, subtree<32> normalisation) against variants. Outputs (ids, probabilities, the two gather
// descriptor arrays) must be bitwise-equal.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet194-expert-diet-engine/detmath.hpp"
#include "harness.hpp"
template<int Width,class F> float subtree(int n,int begin,F get){
 float v[Width];int count=std::min(Width,n-begin);
 for(int i=0;i<count;++i)v[i]=get(begin+i);
 for(int stride=1;stride<Width&&stride<n;stride*=2)
  for(int i=0;i<count;i+=2*stride)v[i]=v[i]+(i+stride<count?v[i+stride]:0.f);
 return v[0];
}
constexpr int N=512,Top=10,MID=640,H=2560;
template<int V> struct KK;
// out layout: ids[Top] (int as float bits? engine puts ints via put); here: ids int[Top], probs float[Top], d2 int[30], d3 int[30]
struct Out {int* ids;float* probs;int* d2;int* d3;uint32_t* error;const uint32_t* active;};
// MODE 0: RouteFast replica. 1: denominator once (lane 0, subtree<32>, same tree) + broadcast. 2: 1 + rank selection.
template<int V,int MODE>
sycl::event route(sycl::queue& q,const float* logits,Out o,int rows){
  return q.submit([&](sycl::handler& h){
   sycl::local_accessor<float,1> ex(N,h),prob(N,h),sums(N/16+1,h);sycl::local_accessor<int,1> bad(1,h);
   sycl::local_accessor<uint32_t,1> cand(2*(N/32)*Top+Top,h);
   h.parallel_for<KK<V>>(sycl::nd_range<1>(size_t(rows)*N,N),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    const int r=int(it.get_group_linear_id()),j=int(it.get_local_linear_id());auto g=it.get_group();
    if(!*o.active||sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*o.error).load())return;
    if(j==0)bad[0]=0;it.barrier(sycl::access::fence_space::local_space);
    const float x=logits[r*N+j];if(!std::isfinite(x))sycl::atomic_ref<int,sycl::memory_order::relaxed,sycl::memory_scope::work_group,sycl::access::address_space::local_space>(bad[0]).store(1);
    it.barrier(sycl::access::fence_space::local_space);
    if(bad[0]){if(j==0)*o.error=1;return;}
    const float maximum=sycl::reduce_over_group(g,x,sycl::maximum<float>());
    ex[j]=detmath::exp(x-maximum);it.barrier(sycl::access::fence_space::local_space);
    constexpr int chunks=(N+15)/16;
    if(j<chunks)sums[j]=subtree<16>(N,j*16,[&](int i){return ex[i];});
    it.barrier(sycl::access::fence_space::local_space);
    float den;
    if constexpr(MODE==0)den=subtree<256>(chunks,0,[&](int i){return sums[i];});
    else {if(j==0)sums[chunks]=subtree<32>(chunks,0,[&](int i){return sums[i];});it.barrier(sycl::access::fence_space::local_space);den=sums[chunks];}
    prob[j]=ex[j]/den;it.barrier(sycl::access::fence_space::local_space);
    if constexpr(MODE==5){ // timing only: MODE 4 selection without the lane-0 output/normalisation tail (WRONG)
     if(j<Top){o.ids[r*Top+j]=j;}
    } else if constexpr(MODE==3){ // timing only: no selection (WRONG outputs)
     if(j<Top){o.ids[r*Top+j]=j;o.probs[r*Top+j]=prob[j];for(int k=0;k<3;++k){o.d2[(r*Top+j)*3+k]=j;o.d3[(r*Top+j)*3+k]=j;}}
     it.barrier(sycl::access::fence_space::global_and_local);
    } else if constexpr(MODE==4){
     // Exact: each subgroup finds its own ten best (larger bits, then lower index) by ten subgroup arg-max rounds; subgroup 0
     // then runs ten arg-max rounds over the 16x10 candidates (5 per lane), giving the same ten in the same order.
     constexpr int SGN=N/32,C=SGN*Top;uint32_t* cbits=cand.get_multi_ptr<sycl::access::decorated::no>().get();uint32_t* cidx=cbits+C;
     auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sgi=int(sg.get_group_linear_id());
     const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);bool taken=false;
     for(int k=0;k<Top;++k){
      const uint32_t top=sycl::reduce_over_group(sg,taken?0u:bits+1u,sycl::maximum<uint32_t>());
      const int index=sycl::reduce_over_group(sg,(!taken&&bits+1u==top)?j:N,sycl::minimum<int>());
      if(j==index){taken=true;cbits[sgi*Top+k]=bits;cidx[sgi*Top+k]=uint32_t(j);}
     }
     it.barrier(sycl::access::fence_space::local_space);
     if(sgi==0){
      constexpr int PER=C/32; // 5
      uint32_t cb[PER],ci[PER];bool tk[PER];
      #pragma unroll
      for(int c=0;c<PER;++c){cb[c]=cbits[lane+32*c];ci[c]=cidx[lane+32*c];tk[c]=false;}
      for(int rank=0;rank<Top;++rank){
       uint32_t best=0;
       #pragma unroll
       for(int c=0;c<PER;++c)best=std::max(best,tk[c]?0u:cb[c]+1u);
       const uint32_t top=sycl::reduce_over_group(sg,best,sycl::maximum<uint32_t>());
       uint32_t mi=uint32_t(N);
       #pragma unroll
       for(int c=0;c<PER;++c)if(!tk[c]&&cb[c]+1u==top)mi=std::min(mi,ci[c]);
       const uint32_t index=sycl::reduce_over_group(sg,mi,sycl::minimum<uint32_t>());
       #pragma unroll
       for(int c=0;c<PER;++c)if(ci[c]==index)tk[c]=true;
       if(lane==0){const float v=prob[index];o.ids[r*Top+rank]=int(index);o.probs[r*Top+rank]=v;
        for(int k=0;k<3;++k){o.d2[(r*Top+rank)*3+k]=k==0?int(index):k==1?0:MID;o.d3[(r*Top+rank)*3+k]=k==0?int(index):k==1?0:H;}}
      }
     }
    } else if constexpr(MODE<2){
     bool taken=false;
     for(int rank=0;rank<Top;++rank){
      const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);
      const uint32_t top=sycl::reduce_over_group(g,taken?0u:bits+1u,sycl::maximum<uint32_t>());
      const int index=sycl::reduce_over_group(g,(!taken&&bits+1u==top)?j:N,sycl::minimum<int>());
      if(j==index)taken=true;
      if(j==0){const float v=prob[index];o.ids[r*Top+rank]=index;o.probs[r*Top+rank]=v;
       for(int k=0;k<3;++k){o.d2[(r*Top+rank)*3+k]=k==0?index:k==1?0:MID;o.d3[(r*Top+rank)*3+k]=k==0?index:k==1?0:H;}}
     }
    } else {
     constexpr int C=(N/32)*Top;uint32_t* cbits=cand.get_multi_ptr<sycl::access::decorated::no>().get();uint32_t* cidx=cbits+C;uint32_t* sel=cidx+C;
     auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sgi=int(sg.get_group_linear_id());
     const uint32_t bits=sycl::bit_cast<uint32_t>(prob[j]);int local=0;
     for(int k=0;k<32;++k){const uint32_t other=sycl::select_from_group(sg,bits,k);local+=other>bits||(other==bits&&k<lane);}
     if(local<Top){cbits[sgi*Top+local]=bits;cidx[sgi*Top+local]=uint32_t(j);}
     it.barrier(sycl::access::fence_space::local_space);
     if(j<C){const uint32_t mb=cbits[j],mi=cidx[j];int rank=0;
      #pragma unroll 8
      for(int c=0;c<C;++c){const uint32_t ob=cbits[c],oi=cidx[c];rank+=ob>mb||(ob==mb&&oi<mi);}
      if(rank<Top)sel[rank]=mi;}
     it.barrier(sycl::access::fence_space::local_space);
     if(j==0)for(int rank=0;rank<Top;++rank){const int index=int(sel[rank]);const float v=prob[index];o.ids[r*Top+rank]=index;o.probs[r*Top+rank]=v;
       for(int k=0;k<3;++k){o.d2[(r*Top+rank)*3+k]=k==0?index:k==1?0:MID;o.d3[(r*Top+rank)*3+k]=k==0?index:k==1?0:H;}}
    }
    if constexpr(MODE!=5){if(j==0){float sum=subtree<32>(Top,0,[&](int i){return o.probs[r*Top+i];});for(int i=0;i<Top;++i)o.probs[r*Top+i]=o.probs[r*Top+i]/sum;}}
   });});
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("device %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  std::mt19937 g(3);std::vector<float> hl(N);for(auto& v:hl)v=std::normal_distribution<float>(0,2)(g);
  hl[17]=hl[200];hl[300]=hl[200]; // ties
  float* lg=sycl::malloc_device<float>(N,q);q.memcpy(lg,hl.data(),N*4).wait();
  // single output buffer so the harness compares everything: ids(10) probs(10) d2(30) d3(30)
  float* y=sycl::malloc_device<float>(80,q);uint32_t* err=sycl::malloc_device<uint32_t>(1,q);uint32_t* act=sycl::malloc_device<uint32_t>(1,q);
  q.fill(err,0u,1).wait();q.fill(act,1u,1).wait();
  Out o{reinterpret_cast<int*>(y),y+10,reinterpret_cast<int*>(y+20),reinterpret_cast<int*>(y+50),err,act};
  Bench B(q,y,80);
  B.add("RouteFast replica",[&]{return route<0,0>(q,lg,o,1);});
  B.add("denominator once",[&]{return route<1,1>(q,lg,o,1);});
  B.add("denominator once + rank select",[&]{return route<2,2>(q,lg,o,1);});
  B.add("timing only: no selection (WRONG)",[&]{return route<3,3>(q,lg,o,1);});
  B.add("subgroup top-10 + subgroup-0 merge",[&]{return route<4,4>(q,lg,o,1);});
  B.add("merge minus selection+tail (WRONG)",[&]{return route<5,5>(q,lg,o,1);});
  B.run(4,10);
}
