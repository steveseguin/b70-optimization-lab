// CPU-only readback of every slab; no exhaustive host math recomputation.
#ifndef HOST_ONLY
#error CPU only
#endif
#define main packet17_census_main
#include "census.cpp"
#undef main
#include <sstream>
int main(int argc,char**argv){using namespace census;
 try{
 if(argc==2&&std::string(argv[1])=="--self-test"){
  // Finite regression that rejects the wrong GNU native-math twin before a
  // long precompute. Volatile input prevents constant folding.
#ifndef __INTEL_LLVM_COMPILER
  throw std::runtime_error("W-A host twin requires IntelLLVM");
#endif
  volatile uint32_t canary=0xbe27ffffu;
  if(bits(evaluate(exp_native,value(canary)))!=0x3f5943afu)throw std::runtime_error("Intel host expf twin canary");

  for(bool explicit_: {false,true})for(size_t n: {size_t(1),size_t(64),size_t(262144)}){
   std::vector<uint32_t> refs(n),got(n);std::vector<Trace> args(explicit_?n:0),actual(n);
   for(size_t i=0;i<n;++i){refs[i]=uint32_t(mix(i));if(explicit_)args[i]={uint32_t(i%14),refs[i],uint32_t(~refs[i]),0};}
   std::stringstream f;write_slab(f,17,refs,args);auto bytes=f.str();
   read_slab(f,17,n,explicit_,got.data(),actual.data());end_slabs(f);
   if(got!=refs||(explicit_&&std::memcmp(actual.data(),args.data(),n*16)))throw std::runtime_error("roundtrip");
   for(int fault=0;fault<3;++fault){std::string bad=bytes;if(fault==0)bad.resize(bad.size()-1);if(fault==1)bad[0]^=1;if(fault==2)bad.back()^=1;std::stringstream stream(bad);bool rejected=false;
    try{read_slab(stream,17,n,explicit_,got.data(),actual.data());}catch(const std::runtime_error&){rejected=true;}if(!rejected)throw std::runtime_error("bad slab accepted");}
  }
  std::cout<<"lossless roundtrip and corrupt/truncated/header rejection passed\n";return 0;
 }
 if(argc!=3)throw std::runtime_error("usage: wa-verify REFERENCES CHUNK");
 std::filesystem::path dir=argv[1];uint64_t chunk=std::stoull(argv[2]);if(chunk<64||chunk>262144||chunk%64)throw std::runtime_error("chunk");
 std::ifstream index(dir/"index.txt");if(!index)throw std::runtime_error("index");std::string file,kind;int op;unsigned domain;uint64_t total,slabs=0,values=0;bool explicit_;
 std::vector<uint32_t> refs(chunk);std::vector<Trace> args(chunk);std::vector<std::string> seen;
 while(index>>file>>op>>domain>>kind>>total>>explicit_){
  if(std::find(seen.begin(),seen.end(),file)!=seen.end())continue;seen.push_back(file);
  std::ifstream f(dir/file,std::ios::binary);
  for(uint64_t start=0;start<total;start+=chunk){uint64_t n=std::min(chunk,total-start);auto [sum,xor_hash]=read_slab(f,start,n,explicit_,refs.data(),args.data());uint64_t actual_sum=0,actual_xor=0;
   for(uint64_t j=0;j<n;++j){uint64_t h=mix((uint64_t(refs[j])<<32)^(start+j));actual_sum+=h;actual_xor^=h;}
   if(actual_sum!=sum||actual_xor!=xor_hash)throw std::runtime_error("host fingerprint mismatch");
   for(uint64_t j: {uint64_t(0),n-1}){Trace t=explicit_?args[j]:Trace{uint32_t(op),input(start+j,domain),bits(1.f),0};int host_op=(t.op==rsqrt_barrier||t.op==rsqrt_corrected)?rsqrt_native:int(t.op);
    if(refs[j]!=bits(evaluate(host_op,value(t.a),value(t.b),value(t.c)))){std::cerr<<file<<" start="<<start<<" j="<<j<<" op="<<host_op<<" a="<<std::hex<<t.a<<" b="<<t.b<<" c="<<t.c<<" stored="<<refs[j]<<" computed="<<bits(evaluate(host_op,value(t.a),value(t.b),value(t.c)))<<std::dec<<std::endl;throw std::runtime_error("host endpoint mismatch");}}
   ++slabs;values+=n;
  }end_slabs(f);
 }
 if(!index.eof()||slabs==0)throw std::runtime_error("incomplete index");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"slabs\":"<<slabs<<",\"values\":"<<values<<",\"endpoint_checks\":"<<2*slabs<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}return 0;
}
