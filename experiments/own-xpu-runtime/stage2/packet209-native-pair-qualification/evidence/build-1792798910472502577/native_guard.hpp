#pragma once
#include "strict_json.hpp"
#include <openssl/evp.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <set>
#include <chrono>
#include <csignal>
#include <ctime>
#include <cctype>
#include <thread>
#include <fcntl.h>
#include <unistd.h>
#include <sched.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
namespace p209 {
namespace fs=std::filesystem;
inline void need(bool ok,const std::string& what){if(!ok)throw std::runtime_error("P209: "+what);}
inline std::string read(const fs::path& p,size_t cap=1024*1024){
  std::ifstream f(p,std::ios::binary);need(bool(f),"read "+p.string());std::string out;char buf[4096];
  while(f){f.read(buf,sizeof(buf));out.append(buf,size_t(f.gcount()));need(out.size()<=cap,"file exceeds bound");}need(f.eof(),"read failed");return out;
}
inline std::string hash(const std::string& value){unsigned char d[32];unsigned n=0;need(EVP_Digest(value.data(),value.size(),d,&n,EVP_sha256(),nullptr)==1&&n==32,"SHA256");std::string s;for(auto b:d){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
inline const CJson& field(const CJson& o,const std::string& k){need(o.kind==CJson::Object,"expected object");auto* v=o.find(k);need(v,"missing field "+k);return *v;}
inline std::string str(const CJson& v){need(v.kind==CJson::String,"expected string");return v.text;}
inline long long integer(const CJson& v){need(v.kind==CJson::Number&&!v.text.empty()&&v.text.size()<19,"expected integer");for(char c:v.text)need(c>='0'&&c<='9',"unsigned integer");return std::stoll(v.text);}
inline bool exists(const fs::path& p){return fs::symlink_status(p).type()!=fs::file_type::not_found;}
inline std::string ticks(pid_t pid){auto s=read("/proc/"+std::to_string(pid)+"/stat",8192);auto end=s.rfind(')');need(end!=std::string::npos,"proc identity");std::istringstream in(s.substr(end+2));std::string t;for(int i=0;i<=19;++i)need(bool(in>>t),"proc fields");return t;}
inline double mono(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
inline void exclusive(const fs::path& path,const std::string& text){int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);need(fd>=0,"exclusive receipt");size_t pos=0;try{while(pos<text.size()){auto n=::write(fd,text.data()+pos,text.size()-pos);need(n>0,"receipt write");pos+=size_t(n);}need(::fsync(fd)==0,"receipt fsync");::close(fd);}catch(...){::close(fd);throw;}}
inline volatile std::sig_atomic_t stopped=0;
inline void stop(int){stopped=1;}
struct Guard {
  fs::path manifest,output,control,root,queue;std::string digest,bytes,boot,parent_ticks;CJson m;pid_t parent;
  Guard(fs::path path,std::string expected):manifest(path),digest(std::move(expected)),parent(getppid()) {
    bytes=read(path);need(hash(bytes)==digest,"manifest hash");
    // Admission serialization is deliberately ASCII JSON; no malformed raw UTF8.
    for(unsigned char c:bytes)need(c<128,"manifest must be ASCII JSON");m=checkpoint_parse_json(bytes);
    need(str(field(m,"schema"))=="packet209.native-admission.v1"&&field(m,"authorized").kind==CJson::Bool&&field(m,"authorized").boolean,"explicit manifest admission");
    need(str(field(m,"bdf"))=="0000:27:00.0"&&str(field(m,"lane"))=="A"&&str(field(m,"window"))=="screen","target admission");
    need(str(field(m,"unit"))=="packet209-native-pair-a","unit identity");
    root="/home/steve/llm-optimizations";queue=root/"experiments/own-xpu-runtime/ops/lane-queue";
    output=root/"experiments/own-xpu-runtime/stage2/packet209-native-pair-qualification/evidence/device-a";
    need(str(field(m,"output"))==output.string(),"fixed output");control=output.string()+".control";
    auto binary=root/"experiments/own-xpu-runtime/stage2/packet209-native-pair-qualification/build/native/paired-qualification";
    need(str(field(m,"binary"))==binary.string(),"fixed binary");
    need(integer(field(m,"root_floor_bytes"))==27000000000LL&&integer(field(m,"write_bytes"))==268435456&&integer(field(m,"host_available_bytes"))==3221225472LL,"resource contract");
    need(str(field(m,"parent_device_image_sha256"))=="e90834e35401eceaa48d1cb9691b6b0bfa56d456e9d57464636140d0c2e3f4a5","P208 device image");
    const auto& e=field(m,"environment");need(e.kind==CJson::Object,"environment");
    const std::set<std::string> names={"PATH","OMP_NUM_THREADS","LD_LIBRARY_PATH","HOME","NEOReadDebugKeys","FilterBdfPath","ZE_ENABLE_PCI_ID_DEVICE_ORDER","ZE_AFFINITY_MASK","ONEAPI_DEVICE_SELECTOR","SYCL_CACHE_DIR","NEO_CACHE_DIR","XDG_CACHE_HOME"};
    need(std::set<std::string>(e.keys.begin(),e.keys.end())==names,"closed environment names");
    for(auto kv:std::vector<std::pair<std::string,std::string>>{{"HOME","/home/steve"},{"FilterBdfPath","0000:27:00.0"},{"ZE_AFFINITY_MASK","0"},{"ONEAPI_DEVICE_SELECTOR","level_zero:0"},{"NEOReadDebugKeys","1"},{"ZE_ENABLE_PCI_ID_DEVICE_ORDER","1"},{"OMP_NUM_THREADS","2"},{"PATH","/usr/bin:/bin"}})need(str(field(e,kv.first))==kv.second,"environment value "+kv.first);
    need(str(field(e,"LD_LIBRARY_PATH"))=="/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib","exact library path");
    for(auto kv:std::vector<std::pair<std::string,std::string>>{{"SYCL_CACHE_DIR","sycl"},{"NEO_CACHE_DIR","neo"},{"XDG_CACHE_HOME","xdg"}})need(str(field(e,kv.first))==(control/"cache"/kv.second).string(),"private cache path");
    boot=str(field(m,"boot_id"));parent_ticks=ticks(parent);
  }
  void live_entry(){
    need(manifest==root/"experiments/own-xpu-runtime/stage2/packet209-native-pair-qualification/READY-FOR-DEVICE.json","fixed operational manifest");
    const auto command=read("/proc/"+std::to_string(parent)+"/cmdline",8192);
    need(command.find((root/"experiments/own-xpu-runtime/stage2/packet209-native-pair-qualification/runner.py").string())!=std::string::npos && command.find("--run")!=std::string::npos,"coordinator parent command");
    need(read("/proc/self/cgroup",8192).find("packet209-native-pair-a.service")!=std::string::npos,"one-shot unit cgroup");
    need(hash(read("/proc/self/exe",256*1024*1024))==str(field(m,"binary_sha256")),"executing binary hash");
    const auto& e=field(m,"environment");extern char** environ;
    for(const auto& name:e.keys){auto* v=::getenv(name.c_str());need(v&&std::string(v)==str(field(e,name)),"live environment "+name);}
    // Validate complete environment in entry.cpp against ::environ.
    struct rlimit limit;need(!getrlimit(RLIMIT_AS,&limit)&&limit.rlim_cur==RLIM_INFINITY&&limit.rlim_max==RLIM_INFINITY,"native AS must be unlimited");
    need(getpriority(PRIO_PROCESS,0)==0,"native Nice0");cpu_set_t cpus;CPU_ZERO(&cpus);need(!sched_getaffinity(0,sizeof(cpus),&cpus),"affinity read");
    for(int i=0;i<CPU_SETSIZE;++i)need(bool(CPU_ISSET(i,&cpus))==(i<4||(i>=16&&i<20)),"native exact affinity");
    need(!p209::exists(output),"fresh native output");struct stat s{};need(!lstat(control.c_str(),&s)&&S_ISDIR(s.st_mode)&&s.st_uid==getuid()&&(s.st_mode&0777)==0700,"private coordinator control");
    need(read("/proc/self/status",65536).find("Umask:\t0077")!=std::string::npos,"private process umask");
    for(const std::string name:{"sycl","neo","xdg"}){struct stat c{};auto path=control/"cache"/name;need(!lstat(path.c_str(),&c)&&S_ISDIR(c.st_mode)&&c.st_uid==getuid()&&(c.st_mode&0777)==0700,"private cache directory");}
    check();
  }
  void check(){
    need(!stopped,"cooperative stop requested");need(getppid()==parent&&ticks(parent)==parent_ticks,"coordinator gone/reused");
    need(hash(read(manifest))==digest,"manifest changed");auto current_boot=read("/proc/sys/kernel/random/boot_id",128);while(!current_boot.empty()&&isspace(current_boot.back()))current_boot.pop_back();need(current_boot==boot,"boot changed");
    need(std::time(nullptr)<=integer(field(m,"expires_unix")),"admission expired");
    for(const std::string lane:{"A","B"}){need(!p209::exists(queue/("STOP-"+lane)),"external STOP");need(hash(read(queue/("PAUSE-"+lane)))==str(field(field(m,"pause_sha256"),lane)),"PAUSE changed");need(hash(read(queue/("queue-"+lane+".txt")))==str(field(field(m,"queue_sha256"),lane)),"queue changed");}
    need(!p209::exists(control/"STOP"),"coordinator STOP");
    std::istringstream in(read(control/"heartbeat",256));std::string pin;double through=0;in>>pin>>through;need(in&&pin==digest&&mono()<=through&&through<=mono()+120,"expired coordinator heartbeat");
  }
  void acknowledged(){double deadline=mono()+30;while(!p209::exists(control/"ACK")){check();need(mono()<deadline,"identity not acknowledged");std::this_thread::sleep_for(std::chrono::milliseconds(20));}need(read(control/"ACK",256)==digest+"\n","identity acknowledgement mismatch");check();}
};
}
