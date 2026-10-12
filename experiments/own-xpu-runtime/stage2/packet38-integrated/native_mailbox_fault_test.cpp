#define main native_equivalence_unused_main
#include "native_controller_test.cpp"
#undef main
int main(){try{
 using namespace native38;int gates=0;std::vector<uint8_t> memory(2*slot_bytes+4096);
 // A missing/stalled peer has a total deadline, independent of futex wakeups.
 {Mailbox box;Backend b(box,memory.data(),1,[](const Request&){return Reply{};},[]{});double start=clock_now();bool failed=false;b.start(1,half);try{b.wait(1);}catch(const std::exception&){failed=true;}require(failed&&clock_now()-start<1.5,"stalled peer bounded timeout");++gates;}
 // A worker failure aborts its peer before either caller may tear down.
 {Mailbox box;std::thread thread([&]{try{worker(box,2,[](const Request&)->Reply{throw std::runtime_error("injected worker failure");},[]{});}catch(...){abort(box);}});
  Backend b(box,memory.data(),2,[](const Request&){return Reply{};},[]{});bool failed=false;try{b.call(1,half);}catch(const std::exception&){failed=true;}thread.join();require(failed&&load(box.abort),"worker failure wakes scheduler");++gates;}
 // Stop callback is checked even when no counter changes, at most 10ms sleep.
 {Mailbox box;double start=clock_now();bool failed=false;try{wait_change(box.request_sequence,0,box,2,[&]{if(clock_now()-start>.03)throw std::runtime_error("stop");});}catch(const std::exception&){failed=true;}require(failed&&clock_now()-start<.25,"stop wait bounded");++gates;}
 // Request termination is acknowledged; subsequent request uses same mapping.
 {Mailbox box;for(int request=0;request<32;++request){std::thread thread([&]{worker(box,2,[](const Request& r){Reply value{};value.token=r.token;return value;},[]{});});Backend b(box,memory.data(),2,[](const Request&){return Reply{};},[]{});require(b.call(1,half,request).token==request,"repeat mailbox payload");b.call(1,0);thread.join();}require(load(box.request_sequence)==64&&load(box.reply_sequence)==64,"repeat mailbox counters");++gates;}
 // A command already published when abort arrives must never be executed.
 {Mailbox box;box.request={half,1,0,0,0,1,{0,0}};publish(box.request_sequence,1);abort(box);bool failed=false,executed=false;
  try{worker(box,2,[&](const Request&){executed=true;return Reply{};},[]{});}catch(const std::exception&){failed=true;}
  require(failed&&!executed,"queued command executed after peer abort");
  Backend b(box,memory.data(),2,[&](const Request&){executed=true;return Reply{};},[]{});failed=false;
  try{b.start(0,half);}catch(const std::exception&){failed=true;}require(failed&&!executed,"local command executed after peer abort");++gates;}
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"gates\":"<<gates<<",\"repeated_requests\":32,\"spin_iterations\":0}"<<std::endl;
}catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}return 0;}
