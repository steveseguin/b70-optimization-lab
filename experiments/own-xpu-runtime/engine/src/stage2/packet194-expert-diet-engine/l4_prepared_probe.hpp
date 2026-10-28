#pragma once
// Narrow host observer for the opt-in L4 diagnostic. Never used in device math.
#include <array>
#include <vector>
#include <cstdint>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iterator>
namespace l4probe {
inline void check(bool ok,const char*why){if(!ok)throw std::runtime_error(std::string("L4 prepared probe: ")+why);}
inline bool enabled(){const char*v=std::getenv("OWNRT_L4_PREP_HISTORY");if(!v)return false;check(std::string(v)=="0"||std::string(v)=="1","option");if(*v=='0')return false;const char*r=std::getenv("OWNRT_L4_RAW_HISTORY");check(r&&std::string(r)=="1","raw history required");return true;}
struct Invocation {int stage;bool prepared;std::array<int,9>shape;std::vector<uintptr_t>pointers;};
struct Context {std::vector<Invocation>calls;};
inline thread_local Context* active=nullptr;
struct Scope {explicit Scope(Context&c){check(!active,"nested observer");active=&c;}~Scope(){active=nullptr;}};
template<class Shape,class P>inline void observe(int stage,const Shape&s,const P&p,bool prepared){if(!active)return;Invocation v{stage,prepared,{s.op,s.tokens,s.width,s.heads,s.extra,s.flags,s.capacity,s.budget,s.extent},{}};for(auto x:p)v.pointers.push_back(reinterpret_cast<uintptr_t>(x));active->calls.push_back(std::move(v));}
inline void validate(const Context&c,const std::vector<std::vector<void*>>&p){check(c.calls.size()==2&&p.size()==2,"exact two actual submissions");for(size_t j=0;j<2;++j){const auto&v=c.calls[j];check(v.stage==(j?0:1)&&v.prepared,"prepared producer then consumer");check(v.shape[1]==1&&v.shape[5]==94&&v.shape[6]==4096,"actual shape/flags");check(v.shape==c.calls[0].shape&&v.pointers.size()==20&&p[j].size()==20,"shape/pointer extents");for(size_t k=0;k<20;++k)check(v.pointers[k]==reinterpret_cast<uintptr_t>(p[j][k]),"actual/prepared pointer identity");}}
inline size_t offset(uintptr_t pointer,uintptr_t base,size_t extent,size_t bytes){check(pointer>=base&&pointer-base<=extent&&bytes<=extent-(pointer-base)&&pointer%4==0,"allocation pointer bounds/alignment");return pointer-base;}
using Bytes=std::vector<uint8_t>;
class History {
 std::filesystem::path dir;std::function<std::string(const Bytes&)>sha;std::ofstream payload,index;int next=0;bool pending=false;
 static Bytes read(const std::filesystem::path&p){std::ifstream f(p,std::ios::binary);check(bool(f),"sealed read");return Bytes(std::istreambuf_iterator<char>(f),{});}
public:
 History(std::filesystem::path p,std::function<std::string(const Bytes&)>h):dir(std::move(p)),sha(std::move(h)){check(std::filesystem::create_directory(dir),"fresh output");payload.open(dir/"prepared.bin",std::ios::binary);index.open(dir/"rows.jsonl");check(bool(payload)&&bool(index),"open");}
 void append(int position,const Bytes&scratch,const std::array<Bytes,5>&controls,const std::string&metadata){check(!pending&&position==next&&next<244&&scratch.size()==4192*4,"row/extent");const size_t sizes[5]={192,192,4,4,4};for(int i=0;i<5;++i)check(controls[i].size()==sizes[i],"control extent");payload.write((const char*)scratch.data(),scratch.size());for(auto&b:controls)payload.write((const char*)b.data(),b.size());index<<"{\"position\":"<<position<<",\"offset\":"<<size_t(next)*17164<<",\"scratch_sha256\":\""<<sha(scratch)<<"\",\"controls_sha256\":[";for(int i=0;i<5;++i)index<<(i?",":"")<<"\""<<sha(controls[i])<<"\"";index<<"],\"invocation\":"<<metadata<<"}\n";payload.flush();index.flush();check(bool(payload)&&bool(index),"write");++next;pending=true;}
 void finish_row(int position){check(pending&&next==position+1,"completed row");pending=false;if(next!=244)return;payload.close();index.close();auto p=read(dir/"prepared.bin"),i=read(dir/"rows.jsonl");check(p.size()==244*17164,"complete payload");std::ofstream f(dir/"seal.json");f<<"{\"schema\":\"ownrt.l4-prepared-history.v1\",\"rows\":244,\"row_bytes\":17164,\"payload_bytes\":"<<p.size()<<",\"payload_sha256\":\""<<sha(p)<<"\",\"index_sha256\":\""<<sha(i)<<"\"}\n";f.flush();check(bool(f),"seal");}
};
}
