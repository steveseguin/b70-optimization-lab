#include "spin_wait.hpp"
#include <cassert>
#include <stdexcept>
#include <vector>
struct Fake {
 using time_point=std::chrono::steady_clock::time_point;
 struct State {time_point t{};int pauses=0,yields=0;std::vector<long> sleeps;};State* s;
 auto now()const{return s->t;}
 void pause(){++s->pauses;s->t+=std::chrono::nanoseconds(500);}
 void yield(){++s->yields;}
 template<class D>void sleep(D d){s->sleeps.push_back(std::chrono::duration_cast<std::chrono::nanoseconds>(d).count());s->t+=d;}
};
int main(){using namespace std::chrono;int checks=0,finishes=0;
 Fake::State s;Fake c{&s};
 assert(p58as::wait([]{return true;},[&]{++checks;},[&]{++finishes;},s.t,c));assert(checks==2&&finishes==1);
 auto end=s.t+microseconds(293);assert(!p58as::wait([]{return false;},[&]{++checks;},[&]{++finishes;},end,c));
 assert(s.t==end&&s.yields==1&&s.pauses==500);assert((s.sleeps==std::vector<long>{20000,20000,3000}));assert(finishes==1);
 s={};assert(p58as::wait([&]{return s.t>=Fake::time_point{}+microseconds(10);},[]{},[&]{++finishes;},Fake::time_point{}+seconds(1),c));assert(s.sleeps.empty());
 bool caught=false;try{p58as::wait([]{return true;},[]{throw std::runtime_error("async");},[]{},s.t,c);}catch(const std::runtime_error&){caught=true;}assert(caught);
 caught=false;try{p58as::wait([]{return true;},[]{},[]{throw std::runtime_error("completion");},s.t,c);}catch(const std::runtime_error&){caught=true;}assert(caught);
 caught=false;try{p58as::wait([]{return false;},[]{throw std::runtime_error("async pending");},[]{},s.t,c);}catch(const std::runtime_error&){caught=true;}assert(caught);
}
