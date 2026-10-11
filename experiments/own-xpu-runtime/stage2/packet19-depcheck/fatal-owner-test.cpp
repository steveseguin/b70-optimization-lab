// Real packet16 owner + packet19 CPU Backend; intentionally faulty submissions.
#include "depcheck.hpp"
#include <iostream>
int main(int argc,char**argv){
 depcheck::setup();std::string mode=argc==2?argv[1]:"";
 auto backend=std::make_unique<depcheck::Backend>();ownrt::Device device(std::move(backend));
 auto id=device.arena.allocate("index",4,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);
 void* p=device.arena.row(id).pointer;depcheck::checker.locate(p,4)->second.name="index";
 ownrt::Operation op;std::array bindings{id};
 try{
  if(mode=="missing-edge"){
   depcheck::checker.strict=true;depcheck::checker.site="orphan-writer";
   // Deliberately emulate an omitted owner ledger edge: this backend submission
   // is real pending work but is absent from Device's predecessor ledger.
   depcheck::checker.submit(0,0,{{p,4,false,true}}, {},[]{std::abort();});
  }else if(mode!="poisoned-index")return 91;
  depcheck::checker.site="index-consumer";
  depcheck::accesses={{p,4,true,false,true}};
  depcheck::closure=[](std::span<void*const>){std::abort();}; // must never run
  auto e=device.compute(op,bindings,{});
  device.wait(e,std::chrono::milliseconds(100));
  return 92; // fault unexpectedly accepted
 }catch(const std::exception& e){
  std::cerr<<"expected checker failure: "<<e.what()<<'\n';
  auto result=device.shutdown(std::chrono::milliseconds(100));
  if(!result.safe_to_exit)ownrt::hold_for_supervisor(); // same call as Engine
  return 93; // a failed owner must not claim a successful drain
 }
}
