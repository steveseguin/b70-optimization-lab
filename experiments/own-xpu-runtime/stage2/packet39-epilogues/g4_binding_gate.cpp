// CPU-only binding gate: no SYCL headers, runtime, discovery, or device binary.
#include "g4_fixture.hpp"
#include "case_runner.hpp"
#include <sys/mman.h>
#include <map>
#include <iostream>
struct HostBackend {
 static constexpr bool binding_only=true;
 std::map<void*,size_t> extents;
 template<class T>T* alloc(size_t n){
  // Reserve the exact full-size banks without touching multi-GB weight pages.
  // Validation inspects addresses/extents, never GEMV data. All small operands
  // are populated through the same fixture path as G4.
  void* p=mmap(nullptr,n*sizeof(T),PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
  if(p==MAP_FAILED)throw std::bad_alloc();extents[p]=n*sizeof(T);return static_cast<T*>(p);
 }
 void copy(void* dst,const void* src,size_t n){std::memcpy(dst,src,n);}
 void wait(){}
 void free(void* p){if(munmap(p,extents.at(p)))throw std::runtime_error("host unmap");extents.erase(p);}
 ~HostBackend(){for(auto [p,n]:extents)munmap(p,n);}
};
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(){try{
 unsigned cases=0,bindings=0,rejections=0;std::cout<<"{\"cases\":[";
 g4_cases([&]<Type T,unsigned K,Kind E,unsigned Split>(const char* name,unsigned rows,double groups,unsigned removed){
  HostBackend host;Fixture<HostBackend> f(host);f.template init<T,K,E>(rows);
  auto original=f.b;
  for(unsigned i=0;i<f.rotations;++i){f.b.w=f.weights[i];f.b.peer=f.peers[i];
   require(host.extents.at(const_cast<uint8_t*>(f.b.w))==f.weight_bytes,"weight extent");
   require(host.extents.at(const_cast<uint8_t*>(f.b.peer))==f.weight_bytes,"peer extent");
   p39::validate<T,K,E,Split>(f.b);++bindings;
  }
  if constexpr(T==Type::Q6_K||T==Type::Q8_0){
   // Both the old codes+scales-only stride and on-disk packed stride must fail.
   for(unsigned rb:{K+4*(K/(T==Type::Q6_K?16:32)),unsigned(K/iq3::layout(T).elements*iq3::layout(T).bytes)}){
    auto b=original;b.rb=rb;bool rejected=false;
    try{p39::validate<T,K,E,Split>(b);}catch(const std::invalid_argument&){rejected=true;}
    require(rejected,"wrong dense row layout admitted");++rejections;
   }
  }
  std::cout<<(cases?",":"")<<"{\"class\":\""<<name<<"\",\"passed\":true,\"row_bytes\":"<<f.b.rb<<",\"columns\":"<<K<<",\"rows\":"<<rows<<",\"split\":"<<Split<<",\"groups_per_token\":"<<groups<<",\"weight_bytes_per_buffer\":"<<f.weight_bytes<<",\"rotations\":"<<f.rotations<<"}";
  f.release();require(host.extents.empty(),"host allocations leaked");++cases;
 });
 unsigned attempted=0,failed=0,cleaned=0;bool durable=false;
 g4_cases([&]<Type T,unsigned K,Kind E,unsigned Split>(const char*,unsigned rows,double,unsigned){
  HostBackend host;Fixture<HostBackend> f(host);++attempted;durable=false;
  bool pass=p39::run_case([&]{f.template init<T,K,E>(rows);if(attempted==6)f.b.rb--;p39::validate<T,K,E,Split>(f.b);if(attempted==7)throw p39::ByteMismatch("injected byte mismatch");},
   [&](const char* kind,const char*){require(std::string(kind)==(attempted==6?"validation":"byte_mismatch"),"failure classification");++failed;durable=true;},
   [&]{if(attempted==6||attempted==7)require(durable,"failure not durable before release");f.release();++cleaned;});
  require(pass==(attempted!=6&&attempted!=7),"case outcome");
 });
 require(attempted==12&&failed==2&&cleaned==12,"did not continue after sixth/seventh cases");
 unsigned infrastructure_attempts=0;bool infrastructure_reported=false,infrastructure_cleaned=false;
 try{g4_cases([&]<Type,unsigned,Kind,unsigned>(const char*,unsigned,double,unsigned){
  ++infrastructure_attempts;p39::run_case([&]{if(infrastructure_attempts==3)throw std::runtime_error("injected infrastructure failure");},
   [&](const char* kind,const char*){require(std::string(kind)=="infrastructure","infrastructure misclassified");infrastructure_reported=true;},
   [&]{if(infrastructure_attempts==3){require(infrastructure_reported,"infrastructure report before cleanup");infrastructure_cleaned=true;}});
 });}catch(const std::runtime_error& e){require(std::string(e.what())=="injected infrastructure failure","unexpected infrastructure error");}
 require(infrastructure_attempts==3&&infrastructure_cleaned,"infrastructure must stop");
 std::cout<<"],\"passed\":true,\"device_executed\":false,\"case_count\":"<<cases<<",\"rotation_bindings\":"<<bindings<<",\"wrong_stride_rejections\":"<<rejections<<",\"continuation_attempted\":"<<attempted<<",\"continuation_failures\":"<<failed<<",\"infrastructure_stopped_at\":"<<infrastructure_attempts<<"}\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
