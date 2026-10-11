// Coordinator only: resident device read/copy ceiling, full deterministic readback.
#include "../kernels.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
using namespace iq3;
namespace {
volatile std::sig_atomic_t stopping=0;
void stop(int){stopping=1;}
auto deadline=std::chrono::steady_clock::time_point::max();
void require(bool b,const char* s){if(!b)throw std::runtime_error(s);}
void admit(){require(!stopping && std::chrono::steady_clock::now()<deadline,"cooperative deadline/stop");}
void wait(ownrt::Device& d,ownrt::Event e){require(d.wait(e,std::chrono::seconds(10)),"event deadline");}
std::string events_json(ownrt::Device& d,const std::vector<ownrt::Event>& events) {
  std::ostringstream s;s<<'[';
  for(size_t i=0;i<events.size();++i){auto t=d.timing(events[i]);s<<(i?",":"")<<"{\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<'}';}
  return s.str()+']';
}
}
int main(int argc,char** argv) {
  if(argc!=5 || std::string(argv[1])!="--authorized-device-window" || std::string(argv[2])!="3")return 2;
  std::signal(SIGINT,stop);std::signal(SIGTERM,stop);deadline=std::chrono::steady_clock::now()+std::chrono::seconds(120);
  std::unique_ptr<ownrt::Device> d;ownrt::Receipt teardown;std::string error,identity;std::vector<std::string> results,censuses;unsigned checks=0;
  try {
    admit();d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(3,true));identity=d->identity();ownrt::CopyEngine copy(*d);
    constexpr size_t chunk=8*1024*1024;
    for(size_t mib:{64,128,256}) {
      admit();size_t bytes=mib*1024*1024;
      auto alloc=[&](const char* name,size_t n,ownrt::Memory m){return d->arena.allocate(name,n,m,m==ownrt::Memory::device?ownrt::Category::scratch:ownrt::Category::pinned_slab,m==ownrt::Memory::device?ownrt::Lifetime::transaction:ownrt::Lifetime::transfer);};
      auto src=alloc("ceiling/src",bytes,ownrt::Memory::device),dst=alloc("ceiling/dst",bytes,ownrt::Memory::device),sums=alloc("ceiling/sums",kopt2::stream_threads*8,ownrt::Memory::device),slab=alloc("ceiling/staging",chunk,ownrt::Memory::pinned);
      censuses.push_back(d->arena.census());auto host=static_cast<uint32_t*>(d->arena.row(slab).pointer);
      for(unsigned salt:{0u,97u}) {
        for(size_t off=0;off<bytes;off+=chunk) {
          admit();for(size_t i=0;i<chunk/4;++i)host[i]=kopt2::stream_word(off/4+i,salt);
          wait(*d,copy.copy(src,off,slab,0,chunk,{}));
        }
        for(bool memcpy:{false,true}) {
          auto submit=[&](){admit();return memcpy?kopt2::device_memcpy(*d,src,dst,bytes):kopt2::streaming_read(*d,src,sums,bytes);};
          wait(*d,submit());std::vector<ownrt::Event> events;
          for(unsigned i=0;i<20;++i){auto e=submit();events.push_back(e);}
          wait(*d,events.back());auto timing=events_json(*d,events);
          if(memcpy) {
            for(size_t off=0;off<bytes;off+=chunk) {
              admit();wait(*d,copy.copy(slab,0,dst,off,chunk,{}));
              for(size_t i=0;i<chunk/4;++i)require(host[i]==kopt2::stream_word(off/4+i,salt),"copy bytes mismatch");
            }
          } else {
            admit();wait(*d,copy.copy(slab,0,sums,0,kopt2::stream_threads*8,{}));
            auto got=reinterpret_cast<const uint64_t*>(host);
            for(size_t l=0;l<kopt2::stream_threads;++l)require(got[l]==kopt2::stream_sum(bytes/4,l,salt),"stream lane sum mismatch");
          }
          ++checks;std::ostringstream s;s<<"{\"variant\":\""<<(memcpy?"device_memcpy":"stream16_sum_u64_v1")<<"\",\"bytes\":"<<bytes<<",\"salt\":"<<salt<<",\"exact\":true,\"events\":"<<timing<<'}';results.push_back(s.str());
        }
      }
      for(auto id:{src,dst,sums,slab})d->arena.release(id);
    }
  }catch(const std::exception& e){error=e.what();}
  if(d){censuses.push_back(d->arena.census());teardown=d->shutdown(std::chrono::seconds(10));}
  std::ofstream census(argv[4]);census<<'[';for(size_t i=0;i<censuses.size();++i)census<<(i?",":"")<<censuses[i];census<<"]\n";
  std::ofstream out(argv[3]);out<<"{\"schema\":\"own-runtime.iq3.packet7.ceiling.v1\",\"device\":"<<ownrt::quote(identity)<<",\"device_properties\":"<<kopt2::device_properties()<<",\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<",\"results\":[";
  for(size_t i=0;i<results.size();++i)out<<(i?",":"")<<results[i];out<<"],\"teardown\":"<<teardown.json()<<"}\n";out.close();
  if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();return !error.empty() || !teardown.safe_to_exit;
}
