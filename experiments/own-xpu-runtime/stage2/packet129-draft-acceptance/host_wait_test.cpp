#include "host_spin.hpp"
#include <atomic>
#include <iostream>
#include <stdexcept>
using Clock=std::chrono::steady_clock;
void check(bool v){if(!v)throw std::runtime_error("wait check failed");}
int main(){try{
 int checks=0,guards=0;
 check(p56x::wait([]{return true;},[&]{++guards;},Clock::now()));check(guards==0);++checks;
 check(!p56x::wait([]{return false;},[&]{++guards;},Clock::now()));check(guards==1);++checks;
 auto start=Clock::now();check(!p56x::wait([]{return false;},[]{},start+std::chrono::milliseconds(2)));
 check(Clock::now()-start<std::chrono::seconds(1));++checks;
 bool caught=false;try{p56x::wait([]{return false;},[]{throw std::runtime_error("cancel/error");},Clock::now()+std::chrono::seconds(1));}catch(const std::runtime_error&){caught=true;}check(caught);++checks;
 // Delayed release/acquire publication with payload, on both sides of spin budget.
 for(int us:{50,2000}){std::atomic<bool> done{false};int payload=0;
  std::thread producer([&]{std::this_thread::sleep_for(std::chrono::microseconds(us));payload=42;done.store(true,std::memory_order_release);});
  bool ready=p56x::wait([&]{return done.load(std::memory_order_acquire);},[]{},Clock::now()+std::chrono::seconds(1));producer.join();check(ready&&payload==42);++checks;}
 // Same-thread draft progress must continue while waiting for target completion.
 int progress=0;check(p56x::wait([&]{return progress==7;},[&]{++progress;},Clock::now()+std::chrono::seconds(1)));++checks;
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"sleep20\":"<<(p56x::sleep20?"true":"false")<<"}\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
