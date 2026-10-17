#include "fixtures.hpp"
#include <omp.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sched.h>
#include <string>

using namespace p46cpu;
namespace {
uint64_t checks=0,hash=1469598103934665603ULL;
void check(bool ok,const char* what){++checks;if(!ok)throw std::runtime_error(what);}
void bits(float got,float expected,const char* what){check(std::bit_cast<uint32_t>(got)==std::bit_cast<uint32_t>(expected),what);}
bool allowed_affinity(const cpu_set_t& mask){
 if(!CPU_COUNT(&mask))return false;
 for(unsigned cpu=0;cpu<CPU_SETSIZE;++cpu)if(CPU_ISSET(cpu,&mask)&&!((cpu>=4&&cpu<=15)||(cpu>=20&&cpu<=31)))return false;
 return true;
}
cpu_set_t worker_affinity(){cpu_set_t mask;CPU_ZERO(&mask);
 if(sched_getaffinity(0,sizeof(mask),&mask)||!allowed_affinity(mask))throw std::runtime_error("worker affinity outside CPUs 4-15,20-31");
 require_environment();return mask;
}
template<Type T> void lane_checks(const Expert& weights,const std::array<uint16_t,hidden>& x){
 Input<hidden> input(x.data());
 for(unsigned row:{0u,1u,17u,319u,639u})for(unsigned projection=0;projection<2;++projection){
  const auto* w=(projection?weights.up:weights.gate).data()+size_t(row)*weights.gate_stride();
  auto got=lanes<T,hidden>(w,input);float ref[32];
  for(unsigned lane=0;lane<32;++lane){
   ref[lane]=p28::expert_lane<T,hidden,false,false>(w,nullptr,x.data(),0,hidden,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{})[0];
   auto packed=p42expert::gate_lane<T,hidden>(w,w,x.data(),0,hidden,lane);
   bits(got[lane],ref[lane],"AVX lane differs from packet28");bits(got[lane],packed[0],"AVX lane differs from packet42");
  }
  bits(iq3::tree32(got.data()),iq3::tree32(ref),"SG32 FP32 reduction differs");
 }
}
template<Type T> void cases(){
 for(unsigned salt:{1u,91u})for(unsigned change:{0u,1u,7u}){
  auto row=p28_scale_fixture(T,salt);auto x=fixture_input(change);Input<hidden> input(x.data());auto got=lanes<T,hidden>(row.data(),input);float expected[32];
  for(unsigned lane=0;lane<32;++lane){expected[lane]=p28::expert_lane<T,hidden,false,false>(row.data(),nullptr,x.data(),0,hidden,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{})[0];bits(got[lane],expected[lane],"finite half-scale edge differs");}
  bits(iq3::tree32(got.data()),iq3::tree32(expected),"finite half-scale tree differs");
 }
 for(unsigned id:{0u,37u,333u}){
  auto weights=fixture_expert(T,id);
  for(unsigned change:{0u,1u,7u}){
   auto x=fixture_input(change);Output got;uint32_t sticky=0;
   check(execute(weights,x,got,sticky),"finite fixture rejected");check(sticky==0,"unexpected sticky error");
   auto ref=oracle<T>(weights,x);
   check(got.gate==ref.gate,"gate BF16 bytes differ");check(got.up==ref.up,"up BF16 bytes differ");
   check(got.activation==ref.activation,"activation BF16 bytes differ");check(got.down==ref.down,"down BF16 bytes differ");
   hash=digest(got,hash);lane_checks<T>(weights,x);
   Input<intermediate> active(got.activation.data());
   for(unsigned row:{0u,1u,1279u,2559u}){auto sums=lanes<Type::IQ4_NL,intermediate>(weights.down.data()+size_t(row)*360,active);float expected[32];
    for(unsigned lane=0;lane<32;++lane){expected[lane]=p33::down_lane<1,intermediate>(weights.down.data()+size_t(row)*360,got.activation.data(),lane);bits(sums[lane],expected[lane],"down lane differs");}
    bits(iq3::tree32(sums.data()),iq3::tree32(expected),"down SG32 reduction differs");
   }
  }
  // Preserve signed zero and gradual underflow. These are finite exact gates.
  for(unsigned mode=0;mode<2;++mode){auto x=fixture_input();constexpr uint16_t special[]={0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};
   for(unsigned k=0;k<hidden;++k)x[k]=special[k%(mode?8:2)];lane_checks<T>(weights,x);}
  // Candidate-only guards: distinguish this evidence from oracle parity.
  Output untouched;untouched.down.fill(0x5577);Output output=untouched;auto x=fixture_input();
  for(uint16_t bad:{uint16_t(0x7f80),uint16_t(0xff80),uint16_t(0x7fc1),uint16_t(0xffc2),uint16_t(0x7f81)}){
   x[3]=bad;uint32_t sticky=0;check(!execute(weights,x,output,sticky),"nonfinite input accepted");check(sticky==1&&output==untouched,"nonfinite guard wrote output");}
  x=fixture_input();uint32_t sticky=7;check(!execute(weights,x,output,sticky)&&sticky==7&&output==untouched,"sticky error changed");sticky=0;
  check(!execute(weights,x,output,sticky,false)&&!sticky&&output==untouched,"inactive changed output");
  auto broken=weights;broken.gate[0]=0x01;broken.gate[1]=0x7c;bool rejected=false;
  try{broken.validate();}catch(const std::invalid_argument&){rejected=true;}check(rejected,"nonfinite scale admitted");
  broken.gate.pop_back();sticky=0;check(!execute(broken,x,output,sticky)&&sticky==1&&output==untouched,"shape error published output");
 }
}
void down_edges(){
 // G4 row 17's packed codes with the existing packet28 finite half-scale
 // edge values. This derived synthetic variant introduces no model bytes.
 auto row=fixture_slice(Type::IQ4_NL,intermediate,1,17);
 constexpr uint16_t scales[]={0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x7bff,0xfbff};
 constexpr uint16_t inputs[]={0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};
 for(auto scale:scales)for(unsigned mode=0;mode<3;++mode){
  for(size_t i=0;i<row.size();i+=18){row[i]=uint8_t(scale);row[i+1]=uint8_t(scale>>8);}
  std::array<uint16_t,intermediate> x{};
  for(unsigned i=0;i<intermediate;++i)x[i]=mode==0?iq3::bf16_bits(float(int(i%17)-8)/32.f):inputs[i%(mode==1?2:8)];
  Input<intermediate> input(x.data());auto got=lanes<Type::IQ4_NL,intermediate>(row.data(),input);float expected[32];
  for(unsigned lane=0;lane<32;++lane){expected[lane]=p33::down_lane<1,intermediate>(row.data(),x.data(),lane);bits(got[lane],expected[lane],"down finite edge lane differs");}
  float result=iq3::tree32(got.data()),reference=iq3::tree32(expected);bits(result,reference,"down finite edge tree differs");
  check(iq3::bf16_bits(result)==iq3::bf16_bits(reference),"down finite edge BF16 differs");
 }
}
void test(){
 require_environment();
 cpu_set_t mask;CPU_ZERO(&mask);check(!allowed_affinity(mask),"empty worker affinity admitted");
 for(unsigned cpu:{4u,15u,20u,31u})CPU_SET(cpu,&mask);
 check(allowed_affinity(mask),"allowed worker affinity rejected");
 for(unsigned cpu:{0u,3u,16u,19u,32u}){CPU_SET(cpu,&mask);check(!allowed_affinity(mask),"escaped worker affinity admitted");CPU_CLR(cpu,&mask);}
 // The fixture slice generator is checked against a direct existing LCG prefix.
 uint32_t state=0x39c0ffee;
 for(unsigned i=0;i<4096;++i){check(advance(0x39c0ffee,i)==state,"fixture jump differs");state=state*1664525u+1013904223u;}
 cases<Type::IQ2_S>();cases<Type::IQ3_S>();down_edges();
 std::cout<<"{\"schema\":\"p46.cpu-expert.exactness.v1\",\"passed\":true,\"checks\":"<<checks<<",\"complete_expert_comparisons\":18,\"expert_ids\":[0,37,333],\"formats\":[\"IQ2_S/IQ4_NL\",\"IQ3_S/IQ4_NL\"],\"input_variants\":3,\"down_finite_edge_cases\":30,\"finite_byte_exact\":true,\"nonfinite_oracle_qualified\":false,\"candidate_guard_tests_passed\":true,\"output_fnv64\":\""<<std::hex<<hash<<std::dec<<"\",\"device_ran\":false,\"device_executed\":false}\n";
}
double percentile(std::vector<double> values,double p){std::sort(values.begin(),values.end());size_t rank=size_t(std::ceil(p*values.size()));return values[rank?rank-1:0];}
void bench(double seconds,unsigned samples,unsigned threads){
 if(seconds<1||seconds>10||samples<3||samples>15||threads<1||threads>24)throw std::invalid_argument("bounded bench requires seconds=1..10, samples=3..15, threads=1..24");
 cpu_set_t affinity=worker_affinity();
 if(unsigned(CPU_COUNT(&affinity))<threads)throw std::runtime_error("more threads than admitted CPUs");
 omp_set_dynamic(0);omp_set_num_threads(threads);
 unsigned environment_errors=0,actual_threads=0;std::vector<cpu_set_t> worker_masks(threads);
 #pragma omp parallel reduction(+:environment_errors)
 {try{auto mask=worker_affinity();unsigned worker=unsigned(omp_get_thread_num());if(worker>=threads)throw std::runtime_error("extra worker");worker_masks[worker]=mask;}catch(...){++environment_errors;}
  #pragma omp single
  actual_threads=unsigned(omp_get_num_threads());
 }
 if(environment_errors)throw std::runtime_error("worker FP environment/affinity invalid");
 if(actual_threads!=threads)throw std::runtime_error("OpenMP did not provide requested workers");
 // 144 distinct expert slices: 141 ordinary and 3 layer-2 experts, exactly 47:1.
 constexpr unsigned count=144;std::vector<Expert> bank;bank.reserve(count);size_t bank_bytes=0;
 for(unsigned id=0;id<count;++id){bank.push_back(fixture_expert(id%48==47?Type::IQ3_S:Type::IQ2_S,id));bank_bytes+=bank.back().bytes();}
 std::vector<Output> outputs(count);std::vector<uint64_t> hashes(count);unsigned iteration=0;
 auto batch=[&](){unsigned failures=0;
  #pragma omp parallel reduction(+:failures)
  {bool admitted=true;
   try{auto mask=worker_affinity();unsigned worker=unsigned(omp_get_thread_num());if(worker>=threads||!CPU_EQUAL(&mask,&worker_masks[worker]))throw std::runtime_error("worker affinity changed");}
   catch(...){admitted=false;++failures;}
   #pragma omp for schedule(static)
   for(unsigned id=0;id<count;++id){if(!admitted)continue;auto input=fixture_input(iteration+id);uint32_t sticky=0;
    if(!execute(bank[id],input,outputs[id],sticky))++failures;hashes[id]=digest(outputs[id]);}
  }
  if(failures)throw std::runtime_error("benchmark expert rejected");++iteration;
 };
 // One initialization sweep is outside timing; no answer/activation reuse.
 batch();std::vector<double> rates,gbps,elapsed;std::vector<unsigned> batches;
 for(unsigned sample=0;sample<samples;++sample){unsigned rounds=0;auto start=std::chrono::steady_clock::now();double duration;
  do{batch();++rounds;duration=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();}while(duration<seconds);
  rates.push_back(double(rounds)*count/duration);gbps.push_back(double(rounds)*bank_bytes/duration/1e9);elapsed.push_back(duration);batches.push_back(rounds);
 }
 uint64_t output_hash=1469598103934665603ULL;for(auto h:hashes)output_hash=digest(&h,sizeof(h),output_hash);
 std::cout<<std::setprecision(12)<<"{\"schema\":\"p46.cpu-expert.throughput.v1\",\"fixture_only\":true,\"device_ran\":false,\"device_executed\":false,\"isa\":\"AVX2\",\"threads\":"<<threads<<",\"affinity_cpus\":[";
 bool first_cpu=true;for(unsigned cpu=0;cpu<CPU_SETSIZE;++cpu)if(CPU_ISSET(cpu,&affinity)){if(!first_cpu)std::cout<<',';std::cout<<cpu;first_cpu=false;}
 std::cout<<"],\"worker_affinity_cpus\":[";
 for(unsigned worker=0;worker<threads;++worker){if(worker)std::cout<<',';std::cout<<'[';bool first=true;for(unsigned cpu=0;cpu<CPU_SETSIZE;++cpu)if(CPU_ISSET(cpu,&worker_masks[worker])){if(!first)std::cout<<',';std::cout<<cpu;first=false;}std::cout<<']';}
 std::cout<<"],\"worker_affinity_checked_each_sweep\":true,\"percentile_definition\":\"nearest-rank actual sample, rank=ceil(p*N), no interpolation\",\"bank_experts\":"<<count<<",\"bank_bytes\":"<<bank_bytes<<",\"ordinary_experts\":141,\"iq3_s_experts\":3,\"bytes_definition\":\"packed gate+up+down bytes processed, not measured DRAM traffic\",\"timing_definition\":\"steady_clock CPU elapsed, includes input permutation, all arithmetic, output checks/hash, OpenMP dispatch\",\"steady_state\":true,\"unrestricted_independent_expert_parallelism\":true,\"layer_latency_measured\":false,\"sample_seconds_minimum\":"<<seconds<<",\"samples\":[";
 for(unsigned i=0;i<samples;++i){if(i)std::cout<<',';std::cout<<"{\"seconds\":"<<elapsed[i]<<",\"batches\":"<<batches[i]<<",\"experts_per_second\":"<<rates[i]<<",\"processed_GB_per_second\":"<<gbps[i]<<'}';}
 std::cout<<"],\"median_experts_per_second\":"<<percentile(rates,.5)<<",\"p10_experts_per_second\":"<<percentile(rates,.1)<<",\"median_processed_GB_per_second\":"<<percentile(gbps,.5)<<",\"p10_processed_GB_per_second\":"<<percentile(gbps,.1)<<",\"output_fnv64\":\""<<std::hex<<output_hash<<std::dec<<"\"}\n";
}
}
int main(int argc,char** argv){try{
 if(argc==2&&std::string(argv[1])=="test")test();
 else if(argc==5&&std::string(argv[1])=="bench")bench(std::stod(argv[2]),std::stoul(argv[3]),std::stoul(argv[4]));
 else throw std::invalid_argument("usage: cpu-expert test | cpu-expert bench SECONDS SAMPLES THREADS");
 return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
