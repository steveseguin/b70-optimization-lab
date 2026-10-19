#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/reply_first.hpp"
#pragma once
#include <chrono>
#include <functional>
#include <ostream>
#include <stdexcept>
#include <utility>
// One owned host report. No device calls and no borrowed per-half stack state.
namespace p92 {
class Reports {
 using Clock=std::chrono::steady_clock;
 std::function<void()> work;
 bool active=false,done=false,sent=false,failed=false,accepted=false;
 int sequence=0,fixture=0,position=0;
 Clock::time_point ready;
 double reply_ms=0,bookkeeping_ms=0;
 void healthy()const{if(failed)throw std::runtime_error("p92 deferred report poisoned");}
 void emit(){
  if(!active||!done||!sent)return;
  if(!output)throw std::runtime_error("p92 diagnostic stream absent");
  *output<<"{\"schema\":\"packet92.host.v1\",\"sequence\":"<<sequence
   <<",\"fixture\":"<<fixture<<",\"position\":"<<position
   <<",\"reply_first\":"<<(enabled?"true":"false")
   <<",\"result_ready_to_reply_ms\":"<<reply_ms
   <<",\"bookkeeping_ms\":"<<bookkeeping_ms<<"}\n";
  if(!*output)throw std::runtime_error("p92 diagnostic write failed");
  active=false;
 }
public:
 bool enabled=false;std::ostream* output=nullptr;
 bool pending()const{return bool(work);}
 bool poisoned()const{return failed;}
 void begin(int seq,int f,int p){
  healthy();emit();if(active||work)throw std::runtime_error("p92 overlapping half report");
  sequence=seq;fixture=f;position=p;done=sent=accepted=false;active=true;
  ready=Clock::now(); // Reply bucket read 1 of 2; after data/error proof.
 }
 void schedule(std::function<void()> fn){
  healthy();if(!active||work||done)throw std::runtime_error("p92 report ownership");
  work=std::move(fn);if(!enabled)flush();
 }
 void published(){
  healthy();if(!active||sent)throw std::runtime_error("p92 publication ownership");
  reply_ms=std::chrono::duration<double,std::milli>(Clock::now()-ready).count(); // 2 of 2
  sent=true;
 }
 void flush(){
  healthy();
  try{
   if(work){
    auto started=Clock::now(); // Bookkeeping bucket read 1 of 2.
    work();
    bookkeeping_ms=std::chrono::duration<double,std::milli>(Clock::now()-started).count(); // 2 of 2
    work={};done=true;
   }
   emit();
  }catch(...){failed=true;throw;} // Never retry a failed report or accept another half.
 }
 // HALF=1, ACCEPT=2, DRAFT=9. Even an already queued half cannot execute
 // until flush succeeds. Accept must precede the only draft overlap window.
 void before(int op){
  healthy();
  if(work&&op==2&&!accepted){accepted=true;return;}
  if(work&&op==9&&accepted)return;
  flush();
 }
 void after(int op){if(op==9)flush();}
};
} // namespace p92
