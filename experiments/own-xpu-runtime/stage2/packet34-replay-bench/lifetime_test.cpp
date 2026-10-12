// CPU ownership model: deliberately has no SYCL/Level Zero includes or linkage.
// Fault injection exercises the packet34 teardown contract, not driver behavior.
#include <algorithm>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>
struct Failure:std::runtime_error{using std::runtime_error::runtime_error;};
static unsigned checks=0;
static void need(bool value,const char* why){++checks;if(!value)throw Failure(why);}
template<class F>static void rejects(F f){bool rejected=false;try{f();}catch(const Failure&){rejected=true;}need(rejected,"required rejection absent");}
struct Owner {
 bool context=true,queue=true,allocated=true,eager=false;
 int graphs=0,events=0,bundles=0,leases=0;
 std::vector<std::string> trace;
 void free(){if(leases||eager)throw Failure("live leases");allocated=false;trace.push_back("free");}
 void close(){if(graphs||events||bundles||leases||eager)throw Failure("borrower survives context");free();queue=false;trace.push_back("queue");context=false;trace.push_back("context");}
};
struct Borrower {
 Owner& owner;int& count;std::string name;
 Borrower(Owner& o,int& c,std::string n):owner(o),count(c),name(std::move(n)){++count;}
 ~Borrower(){if(!owner.context)std::terminate();--count;owner.trace.push_back(name);}
};
struct Command{std::vector<int> values;void run(int& out)const{for(auto v:values)out+=v;}};
struct Recorder {
 Owner& owner;
 std::unique_ptr<Borrower> source,executable,event,bundle;
 bool active=false,pending=false,uncertain=false,clear_started=false,cleared=false;
 int clear_calls=0;
 std::vector<Command> commands;
 explicit Recorder(Owner& o):owner(o){}
 void begin(bool partial_failure=false){
  if(source||owner.eager)throw Failure("begin invalid");
  source=std::make_unique<Borrower>(owner,owner.graphs,"source");++owner.leases;
  if(partial_failure)throw Failure("begin failure before active");active=true;
 }
 void append(const Command& command){if(!active)throw Failure("no capture");commands.push_back(command);}
 void finish(bool fail=false){if(!active)throw Failure("not active");active=false;if(fail)throw Failure("finalize failure");executable=std::make_unique<Borrower>(owner,owner.graphs,"exec");}
 void replay(int& value,bool fail=false){
  if(!executable||pending)throw Failure("replay invalid");
  event.reset();pending=true;uncertain=true;
  if(fail)throw Failure("enqueue uncertainty");
  event=std::make_unique<Borrower>(owner,owner.events,"event");
  for(const auto& command:commands)command.run(value);uncertain=false;
 }
 bool drain(bool completion){if(uncertain||!event&&pending)return false;if(!completion)return false;pending=false;return true;}
 void clear(bool fail=false){
  if(clear_started&&!cleared)throw Failure("no cleanup retry");
  if(pending||uncertain||owner.eager)throw Failure("work not proven complete");
  clear_started=true;++clear_calls;
  if(fail)throw Failure("destruction failure");
  active=false;event.reset();executable.reset();source.reset();bundle.reset();
  if(!cleared)--owner.leases;cleared=true;commands.clear();
 }
};
static void normal(){
 Owner owner;Recorder first(owner),second(owner);
 Command value{{1,2,3}};first.begin();first.append(value);first.finish();second.begin();second.append(value);second.finish();
 value.values.assign(100,9);int state=0;first.replay(state);need(state==6,"value clone mutated");need(first.drain(true),"drain");
 rejects([&]{owner.close();});rejects([&]{owner.free();});
 first.clear();need(owner.leases==1,"shared lease freed");rejects([&]{owner.free();});
 second.replay(state);need(state==12,"second graph");need(second.drain(true),"second drain");second.clear();
 need(owner.events==0&&owner.graphs==0,"wrappers retained");owner.close();
 need(owner.trace.back()=="context","context order");need(!owner.context&&!owner.queue&&!owner.allocated,"owner remained");
}
static void exceptions(){
 {Owner o;Recorder r(o);rejects([&]{r.begin(true);});need(!r.active&&o.leases==1,"partial begin lost lease");r.clear();o.close();}
 {Owner o;Recorder r(o);r.begin();rejects([&]{r.finish(true);});need(o.graphs==1,"failed finalize lost source");r.clear();o.close();}
 {Owner o;Recorder r(o);r.begin();Command c{{3}};r.append(c);r.clear();need(o.graphs==0,"discard capture executed or leaked");o.close();}
 {Owner o;Recorder r(o);r.begin();r.finish();o.eager=true;rejects([&]{r.clear();});need(r.clear_calls==0,"clear started while eager pending");o.eager=false;r.clear();o.close();}
}
static void busy_faults(){
 // Retention is represented by intentionally live ownership until the test's
 // simulated coordinator proves completion; real faults never force this proof.
 {Owner o;Recorder r(o);r.begin();r.finish();int state=0;r.replay(state);need(r.drain(true),"first completion");
  rejects([&]{r.replay(state,true);});need(!r.event,"stale event survived");need(!r.drain(true),"uncertain enqueue accepted");
  rejects([&]{r.clear();});rejects([&]{o.close();});need(o.context&&o.queue&&o.allocated&&o.leases==1,"uncertain owner lost");
  r.pending=false;r.uncertain=false;r.clear();o.close();}
 {Owner o;Recorder r(o);r.begin();r.finish();int value=0;r.replay(value);need(!r.drain(false),"timeout reported complete");
  rejects([&]{r.clear();});rejects([&]{o.close();});need(o.events==1&&o.graphs==2,"busy resource released");need(r.drain(true),"coordinator completion");r.clear();o.close();}
 {Owner o;Recorder r(o);r.begin();r.finish();rejects([&]{r.clear(true);});rejects([&]{r.clear();});need(r.clear_calls==1,"native cleanup retried");
  need(o.graphs==2&&o.leases==1,"failed destroy lost ownership");
  // End model test without simulating a runtime retry: fake resources are
  // discarded only after the independent coordinator adopts this owner.
  r.event.reset();r.executable.reset();r.source.reset();o.leases=0;o.close();}
}
static void escaped_borrowers(){
 for(bool kernel:{false,true}){Owner o;auto b=std::make_unique<Borrower>(o,kernel?o.bundles:o.events,kernel?"bundle":"event");
  rejects([&]{o.close();});need(o.context,"premature context release");b.reset();o.close();}
}
int main(){try{normal();exceptions();busy_faults();escaped_borrowers();std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"device_executed\":false}\n";}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
