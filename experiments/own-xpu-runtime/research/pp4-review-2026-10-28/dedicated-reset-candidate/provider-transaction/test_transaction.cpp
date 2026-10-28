#define PROVIDER_OWNER_FIXTURE_ONLY
#include "test_provider_only_owner.cpp"
#include "pipeline/provider_only/reset_transaction.hpp"
#include <fstream>
namespace fs=std::filesystem;namespace suite=ownrt::provider_only::suite;namespace bulk=ownrt::provider_only::bulk;namespace reset=ownrt::ring_next::reset;
void write(const fs::path&p,const std::string&s){std::ofstream f(p,std::ios::binary);f.write(s.data(),s.size());assert(f);}
std::string digest(const std::string&s){return bulk::hex(bulk::digest_bytes(s.data(),s.size()));}
std::string prompt(int a,int b,int c){std::string s(12,'\0');int32_t words[]={a,b,c};std::memcpy(s.data(),words,12);return s;}
std::string manifest(const fs::path&root){std::string s="{\"schema\":\"ownrt.dedicated-prompt-suite.v1\",\"requests\":12,\"context\":4096,\"max_new\":512,\"model_identity_sha256\":\""+std::string(64,'c')+"\",\"policy_sha256\":\""+std::string(64,'d')+"\"";for(int i=0;i<12;++i){const auto raw=prompt(1+i,2+i,3+i);write(root/("prompt"+std::to_string(i)),raw);auto p="prompt_"+std::to_string(i)+"_";s+=",\""+p+"path\":\""+(root/("prompt"+std::to_string(i))).string()+"\",\""+p+"tokens\":3,\""+p+"sha256\":\""+digest(raw)+"\"";}return s+"}";}
std::string descriptor(const fs::path&root,const reset::PromptAuthority&a,const char*role="target"){return "{\"schema\":\"ownrt.dedicated-reset-request.v2\",\"role\":\""+std::string(role)+"\",\"owner_index\":0,\"global_sequence\":5,\"previous_epoch\":0,\"next_epoch\":1,\"previous_request_sha256\":\""+std::string(64,'a')+"\",\"next_request_sha256\":\""+std::string(64,'b')+"\",\"destination\":\""+(root/"request1").string()+"\",\"oracle\":\"\",\"suite_sha256\":\""+a.suite_sha+"\",\"prompt_sha256\":\""+a.prompt_sha+"\",\"prompt_index\":"+std::to_string(a.index)+",\"prompt_tokens\":"+std::to_string(a.tokens)+"}";}
struct RetainedRuntime:Runtime {
 int resets=0;bool fail_zero=false;
 int live_step(int token,int pos,bool head,const uint8_t* data,size_t n){return canonical(token,pos,head,std::vector<uint8_t>(data,data+n));}
 void reset_request(const fs::path&){++resets;state.position=0;state.extent=32;state.pending=0;state.event=0;state.hidden.clear();for(auto& a:state.allocations)std::fill(a.begin(),a.end(),0);}
 std::string inventory()const{std::string s;for(const auto& a:state.allocations)s+=std::to_string(uintptr_t(a.data()))+":"+std::to_string(a.size())+";";return s;}
 bool cold()const{return !state.position&&!state.pending&&!state.event&&state.hidden.empty()&&std::all_of(state.allocations.begin(),state.allocations.end(),[](const auto&a){return std::all_of(a.begin(),a.end(),[](uint8_t b){return b==0;});});}
};
struct BulkWitness {struct{uint32_t start=0,count=1;}seed;std::vector<uint8_t>hidden=std::vector<uint8_t>(16,7);};
int main(int argc,char**argv){assert(argc==2);fs::path root=fs::absolute(argv[1]);assert(fs::create_directory(root));
 for(int mode=0;mode<7;++mode){auto r=root/std::to_string(mode);fs::create_directory(r);auto raw=manifest(r);write(r/"suite",raw);
  RetainedRuntime runtime;auto c=Fixture{}.context;c.stages=3;c.depth=3;c.request=reset::digest(std::string(64,'a'));
  suite::Suite startup(r/"suite",digest(raw),std::string(64,'c'),std::string(64,'d'),4096,c,true);
  auto prompt=std::make_unique<bulk::Prompt>(r/"prompt0",digest(::prompt(1,2,3)),c);
  provider_only::Owner<RetainedRuntime> owner(runtime,{{"a","b","c"},"draft"},c);
  if(mode==6){Fixture prior;prior.context=c;auto w=witness(prior,3);owner.run(1,w.seed,w.final,w.hidden,true);}else owner.prefill(1,*prompt,BulkWitness{},[](auto&,const uint8_t*,size_t){});assert(owner.serial()==1);
  auto a=startup.authority(1);write(r/"reset",descriptor(r,a,"provider"));auto prepared=startup.prepare(r/"reset",r,c,-1,5,true);
  std::vector<uint8_t> shared(provider_only::wire::shared_bytes,0xa5);int receipts=0,zeroes=0;
  auto zero=[&](auto& rt){++zeroes;++rt.private_zeroes;if(mode==2)throw std::runtime_error("zero failure");};
  auto inventory=[&]{return runtime.inventory()+((mode==3&&runtime.resets)?"changed":"");};
  auto cold=[&]{return runtime.cold()&&mode!=4;};
  auto receipt=[&](const auto&e){++receipts;assert(e.command==5&&e.epoch==1&&e.allocation_before==e.allocation_after&&e.invalidated_bytes==shared.size());assert(std::all_of(shared.begin(),shared.end(),[](auto b){return b==0;}));if(mode==5)throw std::runtime_error("receipt failure");};
  auto run=[&]{provider_only::reset_bulk_owner(owner,prepared,prompt,shared,zero,inventory,cold,receipt,mode!=1);};
  if(mode&&mode!=6){refusal(run);assert(receipts==int(mode==5));assert(owner.failed()==(mode>=2));assert(zeroes==int(mode>=2));if(mode>=2)refusal([&]{owner.prefill(6,*prompt,BulkWitness{},[](auto&,const uint8_t*,size_t){});});continue;}
  run();assert(!owner.failed()&&owner.serial()==0&&runtime.cold()&&receipts==1&&zeroes==1);
  provider_only::wire::Header h;std::memcpy(&h,shared.data(),sizeof h);assert(h.epoch==1&&h.request==prepared.next.request&&h.stream_bytes==16&&h.target_stages==3&&h.depth==3);
  assert(std::all_of(shared.begin()+sizeof h,shared.end(),[](auto b){return b==0;}));
  owner.prefill(6,*prompt,BulkWitness{},[](auto&,const uint8_t*,size_t){});assert(owner.serial()==1);
  // Legacy reset still refuses after the new request uses bulk.
  auto next=prepared.next.request;next[0]^=1;refusal([&]{owner.reset(7,2,next,std::string("unused"),[](auto&d){++d.private_zeroes;});});assert(owner.failed());
 }
 std::cout<<"PASS actual Owner/Sequence bulk-reset transaction, retained allocation pointers, actual Prompt epoch installation, entire publication map cleanup/header, disabled/zero/inventory/cold/receipt failures and poison; synthetic state only, no all-owner barrier\n";
}
