#include "stage2/packet194-expert-diet-engine/l4_prepared_probe.hpp"
#include <cassert>
#include <iostream>
struct Shape {int op=7,tokens=1,width=2560,heads=4,extra=0,flags=94,capacity=4096,budget=2048,extent=0;};
template<class F>void refuses(F f){bool bad=false;try{f();}catch(std::runtime_error&){bad=true;}assert(bad);}
int main(){
 Shape shape;std::vector<void*>p(20);for(int k=0;k<20;++k)p[k]=reinterpret_cast<void*>(0x1000+4*k);
 l4probe::Context c;{l4probe::Scope observing(c);l4probe::observe(1,shape,p,true);l4probe::observe(0,shape,p,true);}l4probe::validate(c,{p,p});assert(!l4probe::active);
 auto wrong=c;wrong.calls[0].stage=0;refuses([&]{l4probe::validate(wrong,{p,p});});
 wrong=c;wrong.calls[1].pointers[19]+=4;refuses([&]{l4probe::validate(wrong,{p,p});});
 wrong=c;wrong.calls[1].shape[5]=78;refuses([&]{l4probe::validate(wrong,{p,p});});
 wrong=c;wrong.calls[1].prepared=false;refuses([&]{l4probe::validate(wrong,{p,p});});
 assert(l4probe::offset(0x1010,0x1000,128,16)==16);
 refuses([]{l4probe::offset(0xffc,0x1000,128,4);});
 refuses([]{l4probe::offset(0x107c,0x1000,128,8);});
 refuses([]{l4probe::offset(0x1001,0x1000,128,4);});
 refuses([&]{l4probe::Scope first(c);l4probe::Scope nested(c);});assert(!l4probe::active);
 std::cout<<"PASS scoped actual-invocation metadata validation; wrong stage/pointer/shape/mode/offset/nesting rejected. Not an Engine or device test.\n";
}
