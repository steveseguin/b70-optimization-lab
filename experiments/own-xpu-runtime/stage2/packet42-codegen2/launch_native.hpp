#pragma once
#include "../packet29-merged/owner.hpp"
#include "../../stage1/packet3-prep/src/sycl_operation.hpp"
#include "compile_smoke.hpp"
#include "gate_mode.hpp"
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <csignal>
namespace p42launch {
struct CaseFailure:std::runtime_error{using std::runtime_error::runtime_error;};
inline volatile std::sig_atomic_t stop_requested=0;
inline void signal_stop(int){stop_requested=1;}
inline void check_stop(){if(stop_requested)throw std::runtime_error("graceful stop requested");}
inline void write(const std::filesystem::path& path,const std::string& value){auto tmp=path;tmp+=".tmp";{std::ofstream f(tmp);f<<value<<'\n';f.flush();if(!f)throw std::runtime_error("receipt write failed (possibly ENOSPC): "+path.string());}std::filesystem::rename(tmp,path);}
inline double median(std::vector<double> v){std::sort(v.begin(),v.end());return(v[(v.size()-1)/2]+v[v.size()/2])/2;}
inline double p90(std::vector<double> v){std::sort(v.begin(),v.end());return v[(9*v.size()+9)/10-1];}
inline std::string array(const std::vector<double>& v){std::ostringstream s;s.precision(17);s<<'[';for(size_t i=0;i<v.size();++i)s<<(i?",":"")<<v[i];s<<']';return s.str();}
inline uint16_t bf(float f){auto u=std::bit_cast<uint32_t>(f);if((u&0x7fffffff)>0x7f800000)return uint16_t((u>>16)|64);return uint16_t((u+0x7fff+((u>>16)&1))>>16);}
struct Runner{
 ownrt::Device d;ownrt::CopyEngine copy;std::vector<ownrt::Allocation> owned;
 explicit Runner(unsigned card):d(ownrt::make_sycl_device(card,true)),copy(d){}
 ownrt::Allocation alloc(size_t bytes,ownrt::Memory m=ownrt::Memory::device){auto a=d.arena.allocate("p42-"+std::to_string(owned.size()),std::max(bytes,size_t(4)),m,ownrt::Category::scratch,ownrt::Lifetime::transaction);owned.push_back(a);return a;}
 void finish(ownrt::Event e){if(!d.wait(e,std::chrono::seconds(3600)))throw std::runtime_error("cooperative event timeout; no retry");}
 void upload(ownrt::Allocation a,const void* src,size_t bytes){auto h=alloc(bytes,ownrt::Memory::pinned);std::memcpy(d.arena.row(h).pointer,src,bytes);finish(copy.copy(a,0,h,0,bytes,{}));d.retire_completed_events();d.arena.release(h);owned.pop_back();}
 void download(ownrt::Allocation a,void* dst,size_t bytes){auto h=alloc(bytes,ownrt::Memory::pinned);finish(copy.copy(h,0,a,0,bytes,{}));std::memcpy(dst,d.arena.row(h).pointer,bytes);d.retire_completed_events();d.arena.release(h);owned.pop_back();}
 double event_us(const std::vector<ownrt::Event>& es){finish(es.back());double value=0;for(auto e:es){auto t=d.timing(e);if(t.end_ns<t.start_ns)throw std::runtime_error("invalid event interval");value+=double(t.end_ns-t.start_ns)*.001;}return value;}
 void clear(){d.retire_completed_events();for(auto a:owned)d.arena.release(a);owned.clear();}
};
struct Options{unsigned card=0,repetitions=200;bool smoke=false;std::filesystem::path output;Options(int argc,char**argv){bool auth=false;for(int i=1;i<argc;++i){std::string v=argv[i];if(v=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(v=="--output"&&i+1<argc)output=argv[++i];else if(v=="--repetitions"&&i+1<argc)repetitions=std::stoul(argv[++i]);else if(v=="--compile-smoke")smoke=true;else if(v=="--authorized-device-window")auth=true;else throw std::runtime_error("invalid argument: "+v);}if(!auth||output.empty()||repetitions!=200)throw std::runtime_error("explicit authorized window, output, 200 repetitions required");std::filesystem::create_directories(output);std::signal(SIGTERM,signal_stop);std::signal(SIGINT,signal_stop);}};
inline int smoke(const Options&o){auto n=p42_compile_smoke(o.card);write(o.output/"receipt.json","{\"passed\":true,\"infrastructure_passed\":true,\"compile_smoke\":true,\"kernel_execution\":false,\"kernels\":"+std::to_string(n)+"}");return 0;}
}
