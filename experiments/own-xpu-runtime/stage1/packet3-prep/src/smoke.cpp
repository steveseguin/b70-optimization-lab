#include "owner.hpp"
#ifdef OWN_RT_HOST_ONLY
#include "mock_device.hpp"
#endif
#include <charconv>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <sys/resource.h>
#include <cstdlib>
using namespace ownrt;
static void write(const std::string& path,const std::string& data) {
  std::ofstream f(path); f << data << '\n'; f.flush();
  if(!f) throw std::runtime_error("receipt write failed");
}
int main(int argc,char** argv) {
  // Validate arguments and priority before even enumerating devices.
  if(argc!=6 || std::string(argv[1])!="--enumerate" || std::string(argv[2])!="--card" || std::string(argv[4])!="--receipt") {
    std::cerr << "usage: own-rt-smoke --enumerate --card N --receipt PATH\n"; return 64;
  }
  auto threads=std::getenv("OMP_NUM_THREADS");
  if(getpriority(PRIO_PROCESS,0)!=19 || !threads || std::string(threads)!="2") return 64;
  std::size_t card=0; std::string card_arg=argv[3];
  auto parse=std::from_chars(card_arg.data(),card_arg.data()+card_arg.size(),card);
  if(parse.ec!=std::errc{} || parse.ptr!=card_arg.data()+card_arg.size()) return 64;
  std::unique_ptr<Device> device;
  try {
#ifdef OWN_RT_HOST_ONLY
    if(card!=0) throw std::out_of_range("mock card");
    auto backend=std::make_unique<MockDevice>(); auto* mock=backend.get();
    std::cout << "0: MockDevice\n";
    device=std::make_unique<Device>(std::move(backend));
#else
    auto cards=enumerate_sycl_cards();
    for(std::size_t i=0;i<cards.size();++i) std::cout << i << ": " << cards[i] << '\n';
    device=std::make_unique<Device>(make_sycl_device(card));
#endif
    auto& arena=device->arena; CopyEngine copies(*device);
    auto weights=arena.allocate("smoke-weights",4096,Memory::device,Category::weights,Lifetime::process);
    auto slab=arena.allocate("smoke-slab",4096,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
    auto output=arena.allocate("smoke-output",4096,Memory::pinned,Category::output_ring,Lifetime::request);
    write(std::string(argv[5])+".census.json",arena.census());
    // Two changing patterns on the same allocations; no model weights.
    for(unsigned pattern:{17,83}) {
      auto* in=static_cast<unsigned char*>(arena.row(slab).pointer);
      for(std::size_t i=0;i<4096;++i) in[i]=static_cast<unsigned char>((i+pattern)%251);
      auto upload=copies.copy(weights,0,slab,0,4096,{});
      auto readback=copies.copy(output,0,weights,0,4096,std::span(&upload,1));
#ifdef OWN_RT_HOST_ONLY
      mock->finish_all();
#endif
      if(!device->wait(readback,std::chrono::seconds(30))) throw std::runtime_error("copy timeout");
      auto* out=static_cast<unsigned char*>(arena.row(output).pointer);
      for(std::size_t i=0;i<4096;++i) if(in[i]!=out[i]) throw std::runtime_error("copy mismatch");
    }
    auto receipt=device->shutdown(std::chrono::seconds(30)); write(argv[5],receipt.json());
    if(!receipt.safe_to_exit) hold_for_supervisor();
    return receipt.exit_code;
  } catch(const std::exception& e) {
    std::cerr << e.what() << '\n';
    if(device) {
      auto receipt=device->shutdown(std::chrono::seconds(30));
      receipt.error=e.what(); receipt.exit_code=1; receipt.status="failed";
      try {write(argv[5],receipt.json());} catch(...) {}
      if(!receipt.safe_to_exit) hold_for_supervisor();
    }
    return 1;
  }
}
