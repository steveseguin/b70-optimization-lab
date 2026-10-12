#include "mock_device.hpp"
#include "owner.hpp"
#include <iostream>
using namespace ownrt;
static void check(bool x){if(!x)throw std::runtime_error("queue isolation test");}
int main(){
 auto backend=std::make_unique<MockDevice>();auto* mock=backend.get();Device d(std::move(backend));
 auto alloc=[&](const char* name){return d.arena.allocate(name,4,Memory::device,Category::scratch,Lifetime::transaction);};
 auto a=alloc("card0:a"),b=alloc("card0:b"),c=alloc("card1:c"),e=alloc("card1:d");
 CopyEngine copy(d);auto first=copy.copy(b,0,a,0,4,{});
 bool rejected=false;try{copy.copy(c,0,b,0,4,{});}catch(const std::logic_error& x){rejected=std::string(x.what()).find("both queues drained")!=std::string::npos;}check(rejected);
 mock->finish(first);
 rejected=false;try{copy.copy(e,0,c,0,4,{});}catch(const std::logic_error& x){rejected=std::string(x.what()).find("foreign-queue")!=std::string::npos;}check(rejected);
 rejected=false;try{copy.copy(e,0,c,0,4,std::span(&first,1));}catch(const std::logic_error& x){rejected=std::string(x.what()).find("foreign-queue")!=std::string::npos;}check(rejected);
 d.retire_completed_events();
 auto peer=copy.copy(c,0,b,0,4,{});mock->finish(peer);d.retire_completed_events();
 auto local=copy.copy(e,0,c,0,4,{});mock->finish(local);d.retire_completed_events();
 check(d.shutdown(std::chrono::milliseconds(100)).safe_to_exit);
 std::cout<<"4/4 peer-drain and foreign-dependency gates PASS\n";
}
