// W0p's production geometry is capacity/rank independent, never shrunk on CPU.
#include "owner.hpp"
#include <sys/mman.h>
#include <fstream>
#include <iostream>
#include <cstring>
#include "audit6_backend.hpp"
int main(){
 ownrt::Device d(std::make_unique<Host>());
 auto local=d.arena.allocate("card0:canary",256,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);
 auto pinned=d.arena.allocate("canary-host",256,ownrt::Memory::pinned,ownrt::Category::pinned_slab,ownrt::Lifetime::transfer);
 ownrt::CopyEngine copy(d,4096,1);
 for(int i=0;i<1000;++i){
  for(auto [dst,src]:{std::pair{local,pinned},std::pair{pinned,local}})
   if(!d.wait(copy.copy(dst,0,src,0,256,{}),std::chrono::seconds(5)))return 1;
  d.retire_completed_events();
 }
 auto end=d.shutdown(std::chrono::seconds(60));
 if(!end.safe_to_exit||end.exit_code||end.live_bytes||end.in_flight)return 1;
 std::cout<<"{\"passed\":true,\"copies\":2000,\"maximum_copy\":256,\"peak_device_bytes\":256,\"device_executed\":false}\n";
}
