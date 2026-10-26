// Host submission cost per kernel: plain nd_range vs a local accessor vs local accessor + group barrier.
#include <sycl/sycl.hpp>
#include <chrono>
#include <cstdio>
template<int V> struct KK;
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{}});
  float* y=sycl::malloc_device<float>(1<<20,q);
  auto plain=[&]{return q.submit([&](sycl::handler& h){h.parallel_for<KK<0>>(sycl::nd_range<1>(4096,64),[=](sycl::nd_item<1> it){y[it.get_global_linear_id()]=1.f;});});};
  auto slm=[&]{return q.submit([&](sycl::handler& h){sycl::local_accessor<float,1> l(16,h);h.parallel_for<KK<1>>(sycl::nd_range<1>(4096,64),[=](sycl::nd_item<1> it){if(it.get_local_linear_id()<16)l[it.get_local_linear_id()]=1.f;y[it.get_global_linear_id()]=l[0];});});};
  auto slmb=[&]{return q.submit([&](sycl::handler& h){sycl::local_accessor<float,1> l(16,h);h.parallel_for<KK<2>>(sycl::nd_range<1>(4096,64),[=](sycl::nd_item<1> it){if(it.get_local_linear_id()<16)l[it.get_local_linear_id()]=1.f;sycl::group_barrier(it.get_group());y[it.get_global_linear_id()]=l[it.get_local_linear_id()%16];});});};
  auto bar=[&]{return q.submit([&](sycl::handler& h){h.parallel_for<KK<3>>(sycl::nd_range<1>(4096,64),[=](sycl::nd_item<1> it){sycl::group_barrier(it.get_group());y[it.get_global_linear_id()]=2.f;});});};
  auto measure=[&](auto f,const char* name){for(int i=0;i<200;++i)f();q.wait();
    for(int rep=0;rep<3;++rep){auto t0=std::chrono::steady_clock::now();for(int i=0;i<500;++i)f();auto t1=std::chrono::steady_clock::now();q.wait();auto t2=std::chrono::steady_clock::now();
    std::printf("  %-28s submit %6.2f us/launch  total %6.2f us/launch\n",name,std::chrono::duration<double,std::micro>(t1-t0).count()/500,std::chrono::duration<double,std::micro>(t2-t0).count()/500);}};
  measure(plain,"plain");measure(slm,"local accessor");measure(slmb,"local accessor + barrier");measure(bar,"barrier only");measure(plain,"plain again");
}
