#include "mock_device.hpp"
#include "owner.hpp"
#include <iostream>
using namespace ownrt;
static void check(bool v){if(!v)throw std::runtime_error("chain invariant");}
int main(){
 auto backend=std::make_unique<MockDevice>();auto* mock=backend.get();Device d(std::move(backend));
 auto a=d.arena.allocate("cardA",4,Memory::device,Category::scratch,Lifetime::transaction);
 auto b=d.arena.allocate("cardB",4,Memory::device,Category::scratch,Lifetime::transaction);
 *static_cast<int*>(d.arena.row(a).pointer)=1729;*static_cast<int*>(d.arena.row(b).pointer)=0;
 CopyEngine copy(d);auto first=copy.copy(b,0,a,0,4,{});auto second=copy.copy(a,0,b,0,4,{});
 bool refused=false;try{mock->finish(second);}catch(const std::logic_error&){refused=true;}check(refused);
 refused=false;try{d.arena.release(a);}catch(const std::logic_error&){refused=true;}check(refused);
 refused=false;try{d.retire_completed_events();}catch(const std::logic_error&){refused=true;}check(refused);
 mock->finish(first);mock->finish(second);check(*static_cast<int*>(d.arena.row(b).pointer)==1729);
 d.retire_completed_events();refused=false;try{d.wait(first,std::chrono::milliseconds(1));}catch(const std::invalid_argument&){refused=true;}check(refused);
 Event last=0;for(int i=0;i<5000;++i)last=copy.copy(i%2?a:b,0,i%2?b:a,0,4,{});
 check(d.in_flight()==5000);mock->finish_all();check(d.wait(last,std::chrono::milliseconds(1)));d.retire_completed_events();
 check(d.shutdown(std::chrono::milliseconds(100)).safe_to_exit);
 std::cout<<"7 deferred chain/lifetime checks PASS; 5000 copies without intervening wait\n";
}
