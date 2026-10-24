#pragma once
#include <chrono>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <thread>
#include <string>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/random.h>
#include <sys/syscall.h>
#include <linux/fs.h>
#include <cerrno>
namespace micro {
// Called only after the real backend is owned by Device, before allocations,
// uploads, capture or measured kernels. No unrelated DRM descriptor is opened.
inline void await_backend_ack(const std::filesystem::path& out){
 auto me=static_cast<long>(::getpid());unsigned char random[16];
 need(::getrandom(random,sizeof(random),0)==sizeof(random),"startup random challenge");
 std::string nonce;for(auto v:random){nonce+="0123456789abcdef"[v>>4];nonce+="0123456789abcdef"[v&15];}
 std::ifstream proc("/proc/self/stat");std::string line;std::getline(proc,line);
 auto close=line.rfind(')');need(close!=std::string::npos,"startup self identity");
 std::istringstream fields(line.substr(close+2));std::string field,ticks;
 for(unsigned number=3;number<=22;++number){need(bool(fields>>field),"startup proc fields");if(number==22)ticks=field;}
 std::string message="GSQ_NATIVE_BACKEND_READY_V1 "+std::to_string(me)+" "+ticks+" "+nonce+"\n";
 auto ready=out/"backend-ready.txt",part=out/"backend-ready.partial",ack=out/"backend-ack.txt";
 int fd=::open(part.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);need(fd>=0,"exclusive backend ready");
 try{need(::write(fd,message.data(),message.size())==ssize_t(message.size())&&!::fsync(fd),"durable backend ready");::close(fd);fd=-1;need(::syscall(SYS_renameat2,AT_FDCWD,part.c_str(),AT_FDCWD,ready.c_str(),RENAME_NOREPLACE)==0,"exclusive atomic ready publication");int parent=::open(out.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW);need(parent>=0,"ready directory");int rc=::fsync(parent);::close(parent);need(!rc,"ready directory sync");}catch(...){if(fd>=0)::close(fd);throw;}
 const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(60);
 while(true){
  guard();need(std::chrono::steady_clock::now()<until,"backend physical-contact ACK deadline");
  int a=::open(ack.c_str(),O_RDONLY|O_NOFOLLOW);
  if(a>=0){
   try{struct stat st{},after{},pathstat{};need(!::fstat(a,&st)&&S_ISREG(st.st_mode)&&st.st_nlink==1&&st.st_uid==::getuid()&&st.st_size==ssize_t(message.size()),"bound ACK extent/owner");
    std::string got(message.size(),'\0');need(::read(a,got.data(),got.size())==ssize_t(got.size()),"complete ACK");
    need(!::fstat(a,&after)&&!::lstat(ack.c_str(),&pathstat)&&same(st,after)&&same(st,pathstat)&&got==message,"ACK challenge/identity unchanged");::close(a);return;
   }catch(...){::close(a);throw;}
  }
  need(errno==ENOENT,"ACK open failure");std::this_thread::sleep_for(std::chrono::milliseconds(20));
 }
}
}
