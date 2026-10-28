#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wreturn-type"
#define PROVIDER_OWNER_FIXTURE_ONLY
#include "test_provider_only_owner.cpp"
#undef PROVIDER_OWNER_FIXTURE_ONLY
#pragma GCC diagnostic pop
#include "pipeline/provider_only/peers.hpp"
#include <fstream>
namespace pipeline {static void transfer(int,void*,size_t,bool,int){throw std::runtime_error("CPU wire test never contacts a device/socket");}}
#include "pipeline/provider_only/runtime.hpp"
struct LoopRuntime:Runtime {
 size_t recursive_bytes=4;int recursive_image=1;
 int live_step(int token,int position,bool head,const uint8_t* hidden,size_t bytes){
  Input input;input.seed.token=token;input.seed.position=position;input.head=head;input.hidden.assign(hidden,hidden+bytes);
  return canonical(token,position,head,input.hidden);
 }
 void reset_request(const std::filesystem::path&){state={};++private_zeroes;}
 void live_dump(const std::filesystem::path&){}
};
struct LoopEngine {
 struct {struct {int vocab=128;}g;}p;
 int stream_bytes()const{return 16;}
 void upload(int,int,size_t,const void*,size_t){}void drain(){}
};
struct LoopOptions {
 std::string pipeline_ring_request_sha256=std::string(64,'0'),provider_bdf="d",provider_replay;
 std::vector<std::string> provider_target_bdfs{"a","b","c"};
 int pipeline_ring_depth=3,channel=-1,seconds=1;
 bool pipeline_ring_recursive_verify=true;
 std::filesystem::path provider_seed_shared,provider_final_shared,output;
};
// Taking the concrete address instantiates every live runtime adapter branch.
[[maybe_unused]] auto instantiate_loop=&provider_only::run_loop<LoopEngine,LoopRuntime,LoopOptions>;
int main(){
 namespace w=ownrt::provider_only::wire;
 {LoopEngine engine;LoopRuntime runtime;LoopOptions options;options.provider_replay="unimplemented";std::vector<uint8_t> shared(w::shared_bytes);
 refusal([&]{provider_only::run_loop(engine,runtime,options,shared.data());});assert(!runtime.canonical_calls);}

 {Fixture fixture;LoopRuntime runtime;auto context=fixture.context;context.stages=3;
 provider_only::Owner<LoopRuntime> owner(runtime,{{"a","b","c"},"d"},context);auto input=witness(fixture,3,false);
 owner.canonical(1,input.seed,input.final,input.hidden);assert(owner.serial()==1&&runtime.position()==1&&runtime.canonical_calls==1);
 refusal([&]{owner.canonical(2,input.seed,input.final,input.hidden);});assert(runtime.canonical_calls==1&&owner.failed());}

 w::Request request;request.op=w::batch_op;request.sequence=1;w::command(request,1);
 request.role=0;refusal([&]{w::command(request,1);});request.role=w::magic;
 request.version_=2;refusal([&]{w::command(request,1);});request.version_=1;
 refusal([&]{w::command(request,2);});request.op=15;refusal([&]{w::command(request,1);});
 char pattern[]="/dev/shm/provider-peer-test-XXXXXX";auto root=std::filesystem::path(::mkdtemp(pattern));assert(!root.empty());
 Fixture fixture;auto input=witness(fixture,3);auto context=fixture.context;context.stages=3;
 std::vector<uint8_t> seed(w::shared_bytes),final(w::shared_bytes);
 std::memcpy(seed.data()+recursive_provider::seed_record_offset,&input.seed,sizeof input.seed);
 std::memcpy(final.data()+recursive_provider::final_record_offset,&input.final,sizeof input.final);
 std::memcpy(final.data()+live_draft::hidden_offset,input.hidden.data(),input.hidden.size());
 // Publication accessor reads the journal marker itself.
 auto write=[&](const char* name,const auto& bytes){std::ofstream out(root/name,std::ios::binary);out.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());};
 write("seed",seed);write("final",final);
 {provider_only::LivePeers peers(root/"seed",root/"final");auto captured=peers.capture(context);assert(captured.hidden==input.hidden);}
 std::filesystem::create_hard_link(root/"seed",root/"alias");
 refusal([&]{provider_only::LivePeers peers(root/"seed",root/"alias");});
 std::filesystem::create_symlink(root/"seed",root/"symlink");
 refusal([&]{provider_only::LivePeers peers(root/"symlink",root/"final");});
 {provider_only::LivePeers peers(root/"seed",root/"final");std::filesystem::rename(root/"seed",root/"old");write("seed",seed);refusal([&]{peers.capture(context);});}
 std::filesystem::remove_all(root);
 std::cout<<"PASS dedicated role/version/sequence/op admission, actual readonly source capture, hardlink/symlink/replaced inode refusal\n";
}
