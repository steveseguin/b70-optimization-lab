#define PROVIDER_OWNER_FIXTURE_ONLY
#include "test_provider_only_owner.cpp"
#include "pipeline/provider_only/prefill.hpp"
#include <fstream>
struct BulkRuntime:Runtime {
 int fail_at=0;
 int live_step(int token,int position,bool head,const void* hidden,size_t bytes){if(position==fail_at){error=true;throw std::runtime_error("partial prefix failure");}return canonical(token,position,head,std::vector<uint8_t>(static_cast<const uint8_t*>(hidden),static_cast<const uint8_t*>(hidden)+bytes));}
};
int main(){
 namespace b=provider_only::bulk;
 auto root=std::filesystem::path("/dev/shm/dedicated-bulk-native-cpu");std::filesystem::create_directory(root);
 auto path=root/"prompt";std::vector<int32_t> tokens={7,10,13,16,19,22,25,28,31,34,37};
 {std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(tokens.data()),tokens.size()*4);}
 auto sha=b::digest_bytes(tokens.data(),tokens.size()*4);Fixture fixture;auto context=fixture.context;context.depth=3;context.stages=3;
 b::Prompt prompt(path,b::hex(sha),context);BulkRuntime runtime;provider_only::Owner<BulkRuntime> owner(runtime,{{"a","b","c"},"d"},context);
 int command=0,trace_count=0;
 for(int start=0;start<9;start+=4){int count=std::min(4,9-start),parity=(start/4)%2;b::Witness w;w.hidden.assign(count*16,42);
  w.seed=b::make(context,prompt,4,++command,start,count,parity,1,tokens.data()+start,w.hidden.data());w.final=b::make(context,prompt,4,command,start,count,parity,2,nullptr,w.hidden.data());
  owner.prefill(command,prompt,w,[&](const auto& row,const auto*,size_t bytes){assert(row.position==++trace_count&&bytes==16);});assert(owner.serial()==uint64_t(start+count));
 }
 assert(runtime.position()==9&&runtime.captures==0&&runtime.restores==0&&trace_count==9);owner.boundary();
 // Every metadata mutation is rejected before any native prefix arithmetic.
 b::Witness witness;witness.hidden.assign(4*16,42);witness.seed=b::make(context,prompt,4,1,0,4,0,1,tokens.data(),witness.hidden.data());witness.final=b::make(context,prompt,4,1,0,4,0,2,nullptr,witness.hidden.data());
 for(int change=0;change<8;++change){auto record=witness.seed;
  if(change==0)record.count=0;if(change==1)record.epoch=1;if(change==2)record.request[0]=1;if(change==3)record.lookahead=2;if(change==4)record.tokens[255]=1;if(change==5)record.stream_bytes=32;if(change==6)record.reserved=1;if(change==7)record.raw_sha[0]=1;
  refusal([&]{b::validate(record,1,context,prompt,4);});
 }
 BulkRuntime broken;broken.fail_at=2;provider_only::Owner<BulkRuntime> bad(broken,{{"a","b","c"},"d"},context);
 refusal([&]{bad.prefill(1,prompt,witness,[](const auto&,const auto*,size_t){});});assert(bad.failed()&&broken.position()==1);
 refusal([&]{bad.prefill(2,prompt,witness,[](const auto&,const auto*,size_t){});});assert(broken.position()==1);
 std::cout<<"PASS actual Owner/Sequence prefix multiplechunks partialtail nohead ownedraw; CPU arithmetic only\n";
}
