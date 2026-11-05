// CPU-only socketpair tests against the transfer function extracted from rank.hpp.
// Run with: python3 test_native_persistent_transport.py
#include <algorithm>
#include <chrono>
#include <cerrno>
#include <cstdint>
#include <future>
#include <iostream>
#include <poll.h>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
#include <vector>

static bool stopped=false;
static int pipeline_stop_fd=-1;
static void require(bool ok,const char* message) { if(!ok)throw std::runtime_error(message); }
#include "rank_transfer_under_test.hpp"
using namespace std::chrono_literals;
struct Pair {
 int fd[2];
 Pair(){require(socketpair(AF_UNIX,SOCK_STREAM,0,fd)==0,"socketpair");}
 ~Pair(){for(int f:fd)if(f>=0)close(f);}
};
template<class F> void fails(F f,const char* expected) {
 try{f();}catch(const std::runtime_error& e){require(std::string(e.what())==expected,"unexpected error");return;}
 throw std::runtime_error("expected failure was absent");
}
int main(){
 // A persistent idle lasts beyond its transfer budget, then accepts bytes.
 {Pair p;auto sent=std::async(std::launch::async,[&]{std::this_thread::sleep_for(1100ms);char x='x';require(send(p.fd[1],&x,1,MSG_NOSIGNAL)==1,"send");});
  char x=0;transfer(p.fd[0],&x,1,false,1,true);sent.get();require(x=='x',"persistent idle receive");}
 // Existing finite-idle behavior is still enforced.
 {Pair p;char x=0;fails([&]{transfer(p.fd[0],&x,1,false,1);},"bounded channel timeout");}
 // A peer that begins but stalls a command must still time out.
 {Pair p;char x='p';require(send(p.fd[1],&x,1,MSG_NOSIGNAL)==1,"partial send");char out[2];
  fails([&]{transfer(p.fd[0],out,2,false,1,true);},"bounded channel timeout");}
 // EOF remains visible both during indefinite idle and during partial input.
 {Pair p;close(p.fd[1]);p.fd[1]=-1;char x=0;
  fails([&]{transfer(p.fd[0],&x,1,false,1,true);},"short/closed channel");}
 {Pair p;char x='p';require(send(p.fd[1],&x,1,MSG_NOSIGNAL)==1,"partial send");shutdown(p.fd[1],SHUT_WR);char out[2];
  fails([&]{transfer(p.fd[0],out,2,false,1,true);},"short/closed channel");}
 // Stop still interrupts an otherwise indefinite idle.
 {Pair p;int stop[2];require(pipe(stop)==0,"pipe");pipeline_stop_fd=stop[0];
  auto signal=std::async(std::launch::async,[&]{std::this_thread::sleep_for(50ms);char x=1;require(write(stop[1],&x,1)==1,"stop write");});
  char x=0;fails([&]{transfer(p.fd[0],&x,1,false,1,true);},"cooperative rank stop");signal.get();
  pipeline_stop_fd=-1;close(stop[0]);close(stop[1]);}
 // Backpressured writes stay bounded; persistent idle cannot be used for writes.
 {Pair p;int size=4096;require(setsockopt(p.fd[0],SOL_SOCKET,SO_SNDBUF,&size,sizeof size)==0,"send buffer");
  std::vector<char> bytes(1024*1024,'w');fails([&]{transfer(p.fd[0],bytes.data(),bytes.size(),true,1);},"bounded channel timeout");
  fails([&]{transfer(p.fd[0],bytes.data(),1,true,1,true);},"bounded transfer budget; persistent idle is receive-only");}
 // Zero is a lifetime setting, never a per-transfer timeout.
 {Pair p;char x=0;fails([&]{transfer(p.fd[0],&x,1,false,0,true);},"bounded transfer budget; persistent idle is receive-only");}
 std::cout<<"PASS: persistent idle, finite expiry, partial timeout, EOF, stop, write timeout, zero-budget rejection\n";
}
