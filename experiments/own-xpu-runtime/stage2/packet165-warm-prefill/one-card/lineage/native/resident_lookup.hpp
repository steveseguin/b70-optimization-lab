// Exact process-owned packed lookup bytes. No page-cache advice or pinning.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <openssl/evp.h>
namespace p58t {
inline void check(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
struct Digest {
  std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)> ctx{EVP_MD_CTX_new(),EVP_MD_CTX_free};
  Digest(){check(ctx&&EVP_DigestInit_ex(ctx.get(),EVP_sha256(),nullptr)==1,"lookup SHA init");}
  void add(const void* p,size_t n){check(EVP_DigestUpdate(ctx.get(),p,n)==1,"lookup SHA update");}
  std::string finish(){unsigned char d[32];unsigned n=0;check(EVP_DigestFinal_ex(ctx.get(),d,&n)==1&&n==32,"lookup SHA finish");std::string s;for(auto b:d){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
};
class ResidentLookup {
  uint8_t* data_=nullptr;size_t bytes_=0;
public:
  std::string source_sha256,resident_sha256;
  ResidentLookup(const ResidentLookup&)=delete;ResidentLookup& operator=(const ResidentLookup&)=delete;
  template<class Reader,class Guard> ResidentLookup(size_t bytes,Reader read,Guard guard):bytes_(bytes) {
    check(bytes>0,"empty resident lookup");
    void* p=mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    check(p!=MAP_FAILED,"resident lookup anonymous allocation failed");data_=static_cast<uint8_t*>(p);
    try {
      Digest source,destination;
      // Bounded source mapping + read buffer, never a second complete copy.
      for(size_t off=0;off<bytes;){guard();size_t n=std::min(bytes-off,size_t(4*1024*1024));auto row=read(off,n);
        check(row.size()==n,"resident lookup short read");source.add(row.data(),n);
        std::memcpy(data_+off,row.data(),n);destination.add(data_+off,n);off+=n;
      }
      source_sha256=source.finish();resident_sha256=destination.finish();
      check(source_sha256==resident_sha256,"resident lookup byte identity failed");
      check(mprotect(data_,bytes_,PROT_READ)==0,"resident lookup read-only protection failed");
    } catch(...) {munmap(data_,bytes_);data_=nullptr;throw;}
  }
  ~ResidentLookup(){if(data_)munmap(data_,bytes_);}
  const uint8_t* slice(size_t off,size_t n) const {check(off<=bytes_&&n<=bytes_-off,"resident lookup bounds");return data_+off;}
  size_t size()const{return bytes_;}
};
}
