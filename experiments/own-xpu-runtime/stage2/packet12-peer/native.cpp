#include "backend.hpp"
#include "cases.hpp"
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sys/resource.h>

namespace {volatile std::sig_atomic_t stopped=0;void stop(int){stopped=1;}}
int main(int argc,char** argv) {
  // Never invoked by validation, even for --help or device enumeration.
  if(argc!=8||std::string(argv[1])!="--authorized-device-window")return 64;
  if(!((std::string(argv[2])=="2"&&std::string(argv[3])=="3")||
       (std::string(argv[2])=="3"&&std::string(argv[3])=="2")))return 64;
  if(getpriority(PRIO_PROCESS,0)!=19||!std::getenv("OMP_NUM_THREADS")||std::string(std::getenv("OMP_NUM_THREADS"))!="2")return 64;
  for(auto key:{"ONEAPI_DEVICE_SELECTOR","SYCL_DEVICE_FILTER","ZE_AFFINITY_MASK"})
    if(std::getenv(key)&&*std::getenv(key))return 64;
  std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
  const std::string output=argv[4],latch=argv[5];
  int seconds=std::stoi(argv[6]);if(seconds<1||seconds>120||std::string(argv[7])!="peer-packet12")return 64;
  auto end=peer::Clock::now()+std::chrono::seconds(seconds);
  auto guard=[&]{if(stopped||std::filesystem::exists(latch)||peer::Clock::now()>=end)throw std::runtime_error("cooperative stop/deadline");};
  std::unique_ptr<ownrt::Device> owner;peer::Backend* backend=nullptr;
  std::vector<std::string> rows;std::string error,teardown="null",census="null",identity;
  bool complete=false,access_ab=false,access_ba=false;
  auto save=[&] {
    std::ofstream f(output);f<<"{\"schema\":\"own-runtime.peer.native.v1\",\"passed\":"<<(complete?"true":"false")
      <<",\"error\":"<<ownrt::quote(error)<<",\"identity\":"<<ownrt::quote(identity)
      <<",\"access_ab\":"<<(access_ab?"true":"false")<<",\"access_ba\":"<<(access_ba?"true":"false")
      <<",\"census\":"<<census<<",\"teardown\":"<<teardown<<",\"cases\":[";
    for(std::size_t i=0;i<rows.size();++i)f<<(i?",":"")<<rows[i];f<<"]}\n";
    if(!f)throw std::runtime_error("receipt write failed");
  };
  try {
    guard();auto b=std::make_unique<peer::Backend>(std::stoi(argv[2]),std::stoi(argv[3]));backend=b.get();
    access_ab=b->access_ab;access_ba=b->access_ba;
    owner=std::make_unique<ownrt::Device>(std::move(b));identity=owner->identity();save();
    peer::cases(*owner,access_ab&&access_ba,[&](int c){backend->allocation_card=c;},guard,
      [&](std::string row){rows.push_back(std::move(row));census=owner->arena.census();save();});
    complete=true;
  } catch(const std::exception& ex) {error=ex.what();std::ofstream(latch)<<error<<'\n';}
  if(owner) {
    census=owner->arena.census();auto r=owner->shutdown(std::chrono::milliseconds(5000));teardown=r.json();
    if(!r.safe_to_exit) {complete=false;error+="; teardown unsafe";std::ofstream(latch)<<error<<'\n';save();ownrt::hold_for_supervisor();}
  }
  save();return complete?0:1;
}
