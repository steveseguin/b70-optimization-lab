// CPU-only reference creation. Sharing census arithmetic does not compile SYCL.
#ifndef HOST_ONLY
#error CPU only
#endif
#define main packet17_original_census_main
#include "census.cpp"
#undef main
#include "wa_storage.hpp"
int main(int argc,char**argv){using namespace census;
 try{
 if(argc!=4)throw std::runtime_error("usage: wa-precompute OUTPUT_DIR TRACE CHUNK");
 std::filesystem::path dir=argv[1];if(std::filesystem::exists(dir))throw std::runtime_error("fresh reference directory required");
 uint64_t chunk=std::stoull(argv[3]);if(chunk<64||chunk>262144||chunk%64)throw std::runtime_error("chunk bound");
 std::filesystem::create_directory(dir);std::ofstream index(dir/"index.txt"),pilots(dir/"coverage.jsonl");
 auto emit=[&](int op,unsigned bits_,const std::string& kind,uint64_t total,bool explicit_,auto make){
  std::string file=kind+"-"+std::to_string(op)+".bin";std::ofstream f(dir/file,std::ios::binary);
  for(uint64_t start=0;start<total;start+=chunk){uint64_t n=std::min(chunk,total-start);std::vector<uint32_t> refs(n);std::vector<Trace> args(explicit_?n:0);
   for(uint64_t j=0;j<n;++j){Trace t=make(start+j);if(explicit_)args[j]=t;int host_op=(t.op==rsqrt_barrier||t.op==rsqrt_corrected)?rsqrt_native:int(t.op);refs[j]=bits(evaluate(host_op,value(t.a),value(t.b),value(t.c)));}write_slab(f,start,refs,args);
  }f.close();if(!f)throw std::runtime_error("reference flush");index<<file<<" "<<op<<" "<<bits_<<" "<<kind<<" "<<total<<" "<<explicit_<<"\n";index.flush();std::cout<<kind<<" "<<names[op]<<" "<<total<<std::endl;
 };
 // Keep the same per-function CPU pilot, selection threshold and coverage.
 // CPU reference evaluation is no longer charged to a device window.
 unsigned rsqrt_bits=32;
 for(int op=exp_native;op<=rsqrt_corrected;++op){if(op==pow_rope)continue;int host_op=op>=rsqrt_barrier?rsqrt_native:op;
  uint32_t pilot_hash=0;auto began=std::clock();for(uint64_t i=0;i<(1ULL<<20);++i)pilot_hash^=bits(evaluate(host_op,value(input(i,20))));
  double cpu=double(std::clock()-began)/CLOCKS_PER_SEC,predicted=cpu*4096;unsigned selected=predicted>550?28:32;
  // All three spellings have the identical host twin. Share the selected domain.
  if(op==rsqrt_native)rsqrt_bits=selected;if(op>=rsqrt_barrier)selected=rsqrt_bits;
  pilots<<"{\"kind\":\"coverage-selection\",\"function\":\""<<names[op]<<"\",\"pilot_inputs\":1048576,\"pilot_cpu_seconds\":"<<cpu<<",\"predicted_full_cpu_seconds\":"<<predicted<<",\"selected_bits\":"<<selected<<",\"pilot_hash\":"<<pilot_hash<<",\"reference_stage\":\"CPU build\",\"reason\":\""<<(op>=rsqrt_barrier?"same host rsqrt twin and coverage as plain":(selected==32?"full enumeration fits projected host budget":"projected full enumeration exceeds 550 CPU seconds"))<<"\"}\n";pilots.flush();
  auto kind=selected==32?"native-exhaustive":"native-stratified";
  if(op>=rsqrt_barrier){index<<kind<<"-3.bin "<<op<<" "<<selected<<" "<<kind<<" "<<(1ULL<<selected)<<" 0\n";continue;}
  emit(op,selected,kind,1ULL<<selected,false,[&](uint64_t i){return Trace{uint32_t(op),input(i,selected),bits(1.f),0};});
 }
 emit(pow_rope,32,"rope-arguments",3*32*151,true,[&](uint64_t k){int op=k%3==0?pow_rope:(k%3==1?sin_native:cos_native);uint64_t point=k/3;float y=-float(2*(point%32))/64.f;float a=op==pow_rope?y:float(point/32)*std::pow(1.e7f,y);return Trace{uint32_t(op),bits(a),0,0};});
 for(int op=division;op<=separate;++op)emit(op,32,"triples",1ULL<<26,true,[&](uint64_t i){float a,b,c;triple(i,a,b,c);return Trace{uint32_t(op),bits(a),bits(b),bits(c)};});
 auto trace=traces(argv[2]);for(auto t:trace)if(t.op>separate)throw std::runtime_error("fixture trace opcode");
 for(int op=exp_native;op<=separate;++op){std::vector<Trace> selected;for(auto t:trace)if(t.op==uint32_t(op))selected.push_back(t);if(!selected.empty())emit(op,32,"actual-fixture-inputs",selected.size(),true,[&](uint64_t i){return selected[i];});}
 // Same short probes for the same-object plain/precise link A/B. Include the
 // cancellation quotient that exposed log-v2 at x=0x3f7ffffe, plus every class.
 for(int op: {int(division),int(sqrt_native),int(rsqrt_native),int(rsqrt_barrier),int(rsqrt_corrected)})
  emit(op,32,"precision-probe",65536,true,[&](uint64_t i){float a,b,c;triple(i,a,b,c);if(op!=division){a=value(input(i,16));b=1.f;c=0.f;}else if(i==0){float m=value(0x3f7ffffeu);a=m-1.f;b=detmath::sum(m,1.f).hi;c=0.f;}return Trace{uint32_t(op),bits(a),bits(b),bits(c)};});
 index.close();pilots.close();std::ofstream done(dir/"complete.json");done<<"{\"complete\":true,\"device_executed\":false,\"chunk\":"<<chunk<<",\"fixture_calls\":"<<trace.size()<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}return 0;
}
