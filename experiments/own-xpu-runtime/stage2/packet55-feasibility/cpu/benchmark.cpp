#include "fixtures.hpp"
#include <omp.h>
#include <sched.h>
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <numeric>

using namespace p55cpu;
using Clock=std::chrono::steady_clock;
namespace {
constexpr unsigned bank_count=96;
constexpr unsigned cpus[]={4,5,6,7,8,9,10,11,12,13,14,15,20,21,22,23};
double percentile(std::vector<double> v,double p){std::sort(v.begin(),v.end());return v.at(size_t(std::ceil(p*v.size()))-1);}
void pin(unsigned thread){
 if(thread>=16)throw std::runtime_error("unexpected worker");
 cpu_set_t before;CPU_ZERO(&before);if(sched_getaffinity(0,sizeof(before),&before)||!CPU_ISSET(cpus[thread],&before))throw std::runtime_error("requested CPU outside inherited affinity");
 cpu_set_t mask;CPU_ZERO(&mask);CPU_SET(cpus[thread],&mask);
 if(sched_setaffinity(0,sizeof(mask),&mask))throw std::runtime_error("worker pin failed");
 require_environment();
}
void verify_pin(unsigned thread){
 cpu_set_t actual;CPU_ZERO(&actual);if(sched_getaffinity(0,sizeof(actual),&actual)||CPU_COUNT(&actual)!=1||!CPU_ISSET(cpus[thread],&actual))throw std::runtime_error("worker affinity drift");require_environment();
}
struct Batch {
 const std::vector<Expert>& bank;
 std::vector<Output> output;
 std::vector<std::array<uint16_t,hidden>> inputs;
 unsigned sequence=0,threads;uint64_t output_hash=1469598103934665603ULL;
 Batch(const std::vector<Expert>& b,unsigned t):bank(b),output(bank_count),inputs(bank_count),threads(t){}
 void run(unsigned count){
  unsigned failures=0;
  const unsigned start=(sequence*10)%bank_count;
  for(unsigned slot=0;slot<count;++slot)inputs[slot]=fixture_input(sequence+slot);
  // Row tiles, not whole experts, are distributed: even a four-miss layer can
  // use all requested threads. The two loops share one team and a barrier.
  #pragma omp parallel num_threads(threads) reduction(+:failures)
  {
   try{verify_pin(unsigned(omp_get_thread_num()));}catch(...){++failures;}
   #pragma omp for schedule(static)
   for(unsigned task=0;task<count*(intermediate/8);++task){
    const unsigned slot=task/(intermediate/8),row=(task%(intermediate/8))*8;const auto& e=bank[(start+slot)%bank_count];
    if(e.format==Type::IQ2_S)gate_rows<Type::IQ2_S>(e,inputs[slot].data(),output[slot],row);
    else gate_rows<Type::IQ3_S>(e,inputs[slot].data(),output[slot],row);
   }
   #pragma omp for schedule(static)
   for(unsigned task=0;task<count*(hidden/8);++task){const unsigned slot=task/(hidden/8),row=(task%(hidden/8))*8;down_rows(bank[(start+slot)%bank_count],output[slot],row);}
   #pragma omp for schedule(static)
   for(unsigned slot=0;slot<count;++slot)if(!finite_output(output[slot]))++failures;
  }
  if(failures)throw std::runtime_error("worker guard/output failed");
  // Include output publication/hash cost and make all computation observable.
  for(unsigned slot=0;slot<count;++slot)output_hash=digest(output[slot],output_hash);
  ++sequence;
 }
};
}
int main(int argc,char** argv){try{
 if(argc!=4)throw std::invalid_argument("usage: cpu-benchmark THREADS SECONDS SAMPLES");
 unsigned threads=std::stoul(argv[1]),samples=std::stoul(argv[3]);double seconds=std::stod(argv[2]);
 if((threads!=1&&threads!=4&&threads!=8&&threads!=12&&threads!=16)||seconds<1||seconds>5||samples<3||samples>7)throw std::invalid_argument("bounded benchmark args");
 omp_set_dynamic(0);omp_set_num_threads(threads);unsigned failures=0,actual=0;
 #pragma omp parallel num_threads(threads) reduction(+:failures)
 {try{pin(unsigned(omp_get_thread_num()));}catch(...){++failures;}
  #pragma omp single
  actual=omp_get_num_threads();
 }
 if(failures||actual!=threads)throw std::runtime_error("worker affinity/FP guard failed");
 std::cout<<std::setprecision(12)<<"{\"schema\":\"p55.cpu-throughput.v1\",\"device_executed\":false,\"synthetic_fixture\":true,\"threads\":"<<threads<<",\"worker_cpus\":[";
 for(unsigned i=0;i<threads;++i){if(i)std::cout<<',';std::cout<<cpus[i];}
 std::cout<<"],\"physical_cores\":"<<std::min(threads,12u)<<",\"smt_siblings\":"<<(threads>12?threads-12:0)
  <<",\"bank_count\":96,\"max_packed_bank_bytes\":223641600,\"pinned_host_bytes\":0,\"dram_bandwidth_measured\":false,\"ordinary_layer_count\":47,\"iq3_s_layer_count\":1,\"timing\":\"host steady_clock: input fill, OpenMP team dispatch, both row loops/barrier, finite checks, output hash; allocation/admission excluded\",\"percentiles\":\"nearest rank actual sample; no interpolation\",\"cases\":[";
 bool first=true;
 for(Type format:{Type::IQ2_S,Type::IQ3_S}){
  std::vector<Expert> bank;bank.reserve(bank_count);for(unsigned id=0;id<bank_count;++id)bank.push_back(fixture_expert(format,id));
  Batch batch(bank,threads);const size_t expert_bytes=bank[0].bytes();
  for(unsigned misses:{96u,4u,6u,10u}){
   // Fill a complete >LLC bank once, then rotate all timing calls through it.
   // No result/activation reuse; changing inputs on every call.
   batch.run(bank_count);
   std::vector<double> rate,latency;
   if(!first)std::cout<<',';first=false;
   std::cout<<"{\"format\":\""<<(format==Type::IQ2_S?"IQ2_S/IQ4_NL":"IQ3_S/IQ4_NL-layer2")<<"\",\"expert_bytes\":"<<expert_bytes<<",\"bank_bytes\":"<<expert_bytes*bank_count
    <<",\"experts_per_dispatch\":"<<misses<<",\"layer_latency_measured\":"<<(misses==96?"false":"true")<<",\"samples\":[";
   for(unsigned sample=0;sample<samples;++sample){
    std::vector<double> durations;const auto begin=Clock::now();double elapsed=0;unsigned calls=0;
    do{const auto a=Clock::now();batch.run(misses);const auto b=Clock::now();durations.push_back(std::chrono::duration<double,std::micro>(b-a).count());++calls;elapsed=std::chrono::duration<double>(b-begin).count();}while(elapsed<seconds);
    double gbps=double(calls)*misses*expert_bytes/elapsed/1e9,us=elapsed*1e6/calls;
    rate.push_back(gbps);latency.push_back(us);
    if(sample)std::cout<<',';std::cout<<"{\"seconds\":"<<elapsed<<",\"calls\":"<<calls<<",\"packed_GB_s\":"<<gbps<<",\"us_per_expert\":"<<us/misses<<",\"dispatch_mean_us\":"<<us<<",\"dispatch_p50_us\":"<<percentile(durations,.5)<<",\"dispatch_p90_us\":"<<percentile(durations,.9)<<",\"dispatch_p99_us\":"<<percentile(durations,.99)<<'}';
   }
   std::cout<<"],\"median_packed_GB_s\":"<<percentile(rate,.5)<<",\"median_us_per_expert\":"<<percentile(latency,.5)/misses<<",\"median_dispatch_us\":"<<percentile(latency,.5)<<",\"output_fnv64\":\""<<std::hex<<batch.output_hash<<std::dec<<"\"}";
  }
 }
 std::cout<<"]}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
