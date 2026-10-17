// CPU-only: actual P39 owner, full production fixture geometry, no arithmetic.
#include "p39_fixture.cpp"
#include <sys/mman.h>
#include <iostream>
struct ExtentBackend:ownrt::Backend {
 std::map<void*,size_t> sizes;size_t copies=0,bytes=0,maximum=0;
 std::string identity()const override{return "CPU full-extent mock";}
 void* allocate(size_t n,ownrt::Memory)override{
  void*p=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_NORESERVE,-1,0);
  if(p==MAP_FAILED)throw std::bad_alloc();sizes[p]=n;return p;
 }
 void release(void*p,ownrt::Memory)override{munmap(p,sizes.at(p));sizes.erase(p);}
 ownrt::Event copy(void*,const void*,size_t n,std::span<const ownrt::Event>)override{
  ++copies;bytes+=n;maximum=std::max(maximum,n);return next_handle();
 }
 ownrt::Event marker(std::span<const ownrt::Event>)override{return next_handle();}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>)override{throw std::logic_error("extent gate cannot compute");}
 bool complete(ownrt::Event)override{return true;}bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 ownrt::EventTiming timing(ownrt::Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
int main(){
 // Byte-level checks on both slab boundaries and both transfer directions.
 unsigned byte_cases=0,rejections=0;
 {
  OwnerBackend q(0);
  for(size_t n:{size_t(1),size_t(4*1024*1024-1),size_t(4*1024*1024),size_t(4*1024*1024+19)}){
   std::vector<uint8_t> source(n),result(n);for(size_t i=0;i<n;++i)source[i]=uint8_t(i*17+i/251);
   auto a=q.alloc<uint8_t>(n),b=q.alloc<uint8_t>(n);
   q.copy(a,source.data(),n);q.copy(b,a,n);q.copy(result.data(),b,n);
   if(result!=source)throw std::runtime_error("slab bytes/offsets differ");
   q.free(a);q.free(b);++byte_cases;
  }
  auto a=q.alloc<uint8_t>(8),b=q.alloc<uint8_t>(8);auto aid=q.id(a),bid=q.id(b);
  auto reject=[&](size_t off,size_t soff,size_t n){try{q.copier.copy(aid,off,bid,soff,n,{});}catch(const std::out_of_range&){++rejections;return;}throw std::runtime_error("copy guard weakened");};
  reject(0,0,0);reject(0,0,128ull*1024*1024+1);reject(7,0,2);reject(0,7,2);
  q.free(b);reject(0,0,1);q.free(a);
  auto end=q.d.shutdown(std::chrono::seconds(60));if(!end.safe_to_exit||end.exit_code)throw std::runtime_error("byte test teardown");
 }
 unsigned cases=0,failed=0;
 g4_cases([&]<Type T,unsigned K,Kind E,unsigned Split>(const char*name,unsigned rows,double,unsigned){
  if constexpr(E==Kind::expert_act||E==Kind::gdn_conv)return;
  else {
   auto backend=std::make_unique<ExtentBackend>();auto* trace=backend.get();OwnerBackend q(std::move(backend));
   P39Fixture<OwnerBackend> f(q);
   const size_t bank=integrated::arithmetic::row_bytes(T,K,(T==Type::Q6_K||T==Type::Q8_0)?6:2)*size_t(rows)*(E==Kind::expert_checks||E==Kind::down_status?512:1);
   bool passed=true;std::string error;
   try{f.template init<T,K,E>(rows,true);f.reset();auto snapshot=f.snapshot();f.release();}
   catch(const std::exception&e){passed=false;error=e.what();++failed;}
   auto end=q.d.shutdown(std::chrono::seconds(60));if(!end.safe_to_exit||end.exit_code)throw std::runtime_error("extent teardown");
   std::cout<<"{\"class\":\"fusion:p39."<<name<<"\",\"bank_bytes\":"<<bank<<",\"rows\":"<<rows<<",\"rotations\":"<<f.rotations<<",\"copies\":"<<trace->copies<<",\"copy_bytes\":"<<trace->bytes<<",\"maximum_copy\":"<<trace->maximum<<",\"passed\":"<<(passed?"true":"false")<<",\"error\":"<<ownrt::quote(error)<<"}\n";++cases;
  }
 });
 std::cout<<"{\"passed\":"<<(failed?"false":"true")<<",\"cases\":"<<cases<<",\"failures\":"<<failed<<",\"byte_cases\":"<<byte_cases<<",\"guard_rejections\":"<<rejections<<",\"device_executed\":false}\n";
 return failed?1:0;
}
