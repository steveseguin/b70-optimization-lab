// CPU-only regression controls linked to the exact owner and submitters.
#ifndef P42_BINDING_GATE
#error This program is a host-only admission gate
#endif
#include "extras_native.hpp"
#include <functional>
using namespace ownrt;
int main(){try{
 Device d(make_sycl_device(2,true));CopyEngine copies(d);unsigned checks=0;
 auto alloc=[&](size_t n,Memory m=Memory::device){return d.arena.allocate("negative-"+std::to_string(next_handle()),std::max(n,size_t(4)),m,Category::scratch,Lifetime::transaction);};
 auto rejects=[&](const std::string& message,auto call){bool caught=false;try{call();}catch(const std::exception&e){caught=std::string(e.what()).find(message)!=std::string::npos;if(!caught)throw;}if(!caught)throw std::runtime_error("negative control accepted: "+message);++checks;};
 Operation op;auto a=alloc(64),h=alloc(64,Memory::pinned);
 rejects("empty compute bindings",[&]{d.compute(op,{},{});});
 rejects("live device allocation",[&]{std::array b{h};d.compute(op,b,{});});
 auto released=alloc(64);d.arena.release(released);
 rejects("live device allocation",[&]{std::array b{released};d.compute(op,b,{});});
 rejects("copy extent",[&]{copies.copy(a,0,h,0,65,{});});
 rejects("aliased copy",[&]{copies.copy(a,0,a,0,4,{});});
 // Positive control: this exact owner accepts a real binding.
 std::array good{a};auto e=d.compute(op,good,{});if(!d.wait(e,std::chrono::seconds(1)))throw std::runtime_error("positive owner control");d.retire_completed_events();
 auto fixtures=p42extras::fixtures();auto found=std::find_if(fixtures.begin(),fixtures.end(),[](auto& f){return f.s.op==ng::norm;});if(found==fixtures.end())throw std::runtime_error("norm fixture missing");auto f=*found;std::array<Allocation,19> bound;
 for(unsigned j=0;j<19;++j)bound[j]=alloc(f.data[j].size());
 auto scratch=alloc(std::max(specialised::scratch_floats(f.s),round2::scratch_floats(f.s))*4);
 auto& row=const_cast<Row&>(d.arena.row(bound[0]));auto saved=row;
 row.bytes=1;
 rejects("extent/memory/alignment",[&]{p42extras::submit<32>(d,f.s,bound,scratch);});row=saved;
 row.pointer=static_cast<char*>(saved.pointer)+1;
 rejects("extent/memory/alignment",[&]{p42extras::submit<32>(d,f.s,bound,scratch);});row=saved;
 rejects("scratch alias",[&]{p42extras::submit<32>(d,f.s,bound,bound[0]);});
 auto alias=bound;alias[2]=alias[0];
 rejects("writable binding alias",[&]{p42extras::submit<32>(d,f.s,alias,scratch);});
 auto state=d.shutdown(std::chrono::seconds(1));if(!state.safe_to_exit||state.exit_code)throw std::runtime_error("negative teardown");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"rejection_checks\":"<<checks<<",\"positive_bound_submission\":true}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
