#pragma once
// Sparse CPU storage. Owner performs the unchanged extent/lifetime checks.
// Only small control transfers carry bytes; arithmetic is deliberately absent.
class Host final: public ownrt::Backend {
 std::map<void*,size_t> sizes;
public:
 inline static Host* current=nullptr;
 Host(){current=this;}
 size_t copies=0,maximum=0,total=0;
 std::string identity()const override{return "audit6 sparse CPU; no weight payload";}
 void* allocate(size_t n,ownrt::Memory)override {
  auto p=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_NORESERVE,-1,0);
  if(p==MAP_FAILED)throw std::bad_alloc();sizes[p]=n;return p;
 }
 void release(void*p,ownrt::Memory)override {munmap(p,sizes.at(p));sizes.erase(p);}
 ownrt::Event copy(void*a,const void*b,size_t n,std::span<const ownrt::Event>)override {
  ++copies;maximum=std::max(maximum,n);total+=n;
  if(n<=65536)std::memcpy(a,b,n);return ownrt::next_handle();
 }
 ownrt::Event marker(std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation>,std::span<void*const>)override{return [this]{return ownrt::next_handle();};}
 bool complete(ownrt::Event)override{return true;}
 bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 ownrt::EventTiming timing(ownrt::Event)override{return {};}
 void synchronize()override{} void clear_events()override{} void close_queue()override{} void close_context()override{}
};

inline size_t audit_payload_bytes=0;
inline void audit_write(std::ofstream&,const char*,std::streamsize n){audit_payload_bytes+=size_t(n);}
