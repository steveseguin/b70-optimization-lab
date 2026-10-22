#pragma once
#include <chrono>
#include <thread>
namespace p58as {
// Owner-thread policy only; switched at an already drained view boundary.
inline thread_local bool spin_enabled=false;
struct Clock {
 using time_point=std::chrono::steady_clock::time_point;
 auto now() const {return std::chrono::steady_clock::now();}
 void pause() const {
#if defined(__x86_64__) || defined(__i386__)
 __builtin_ia32_pause();
#else
 std::this_thread::yield();
#endif
 }
 void yield() const {std::this_thread::yield();}
 template<class D> void sleep(D delay) const {std::this_thread::sleep_for(delay);}
};
// Independent reimplementation of packet56x sleep20 semantics. One budget.
template<class Ready,class Error,class Finish,class C=Clock>
bool wait(Ready ready,Error error,Finish finish,typename C::time_point deadline,C clock={}) {
 const auto spin_end=clock.now()+std::chrono::microseconds(250);
 unsigned iterations=0;
 for(;;) {
  error();
  if(ready()){finish();error();return true;}
  const auto now=clock.now();if(now>=deadline)return false;
  if(now<spin_end){clock.pause();if(++iterations%256==0)clock.yield();}
  else {auto delay=std::chrono::duration_cast<typename C::time_point::duration>(std::chrono::microseconds(20));if(deadline-now<delay)delay=deadline-now;clock.sleep(delay);}
 }
}
}
