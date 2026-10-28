#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wreturn-type"
#define PROVIDER_OWNER_FIXTURE_ONLY
#include "test_provider_only_owner.cpp"
#undef PROVIDER_OWNER_FIXTURE_ONLY
#pragma GCC diagnostic pop
#include "pipeline/provider_only/peers.hpp"
#include <fstream>
#include <functional>
namespace pipeline {static std::function<void(void*,size_t,bool)> transport;static void transfer(int,void* bytes,size_t size,bool send,int){assert(transport);transport(bytes,size,send);}}
#include "pipeline/provider_only/runtime.hpp"
struct LoopRuntime:Runtime {
 std::function<void()> prefill_hook;
 size_t recursive_bytes=4;int recursive_image=1;
 int live_step(int token,int position,bool head,const uint8_t* hidden,size_t bytes){
  if(prefill_hook){auto hook=std::move(prefill_hook);prefill_hook={};hook();for(size_t i=0;i<bytes;++i)assert(hidden[i]==42);}
  Input input;input.seed.token=token;input.seed.position=position;input.head=head;input.hidden.assign(hidden,hidden+bytes);
  return canonical(token,position,head,input.hidden);
 }
 void reset_request(const std::filesystem::path&){state={};++private_zeroes;}
 std::vector<std::filesystem::path> dumps;
 void live_dump(const std::filesystem::path& path){dumps.push_back(path);}
};
struct LoopEngine {
 struct {struct {int vocab=128;}g;}p;
 int stream_bytes()const{return 16;}
 void upload(int,int,size_t,const void*,size_t){}void drain(){}
};
struct LoopOptions {
 std::string pipeline_ring_request_sha256=std::string(64,'0'),provider_bdf="d",provider_replay;
 std::vector<std::string> provider_target_bdfs{"a","b","c"};
 int pipeline_ring_depth=3,channel=-1,seconds=1,prefill_rows=0,prefill_slots=2;
 std::filesystem::path provider_prefill_prompt,provider_prefill_seed_shared,provider_prefill_final_shared;std::string provider_prefill_prompt_sha256;
 bool pipeline_ring_recursive_verify=true,provider_capture_ready=false;
 std::filesystem::path provider_seed_shared,provider_final_shared,output;
};
// Taking the concrete address instantiates every live runtime adapter branch.
[[maybe_unused]] auto instantiate_loop=&provider_only::run_loop<LoopEngine,LoopRuntime,LoopOptions>;
// Build actual-format journals for later canonical positions, preserving the
// original tentative bit and raw fixture ordinal after the independent ACCEPT.
Witness later_witness(const Input& in,const Row& previous){
 Witness out;out.hidden=in.hidden;auto& seed=out.seed;auto& m=seed.row;const auto& row=in.seed;
 seed.published_sequence=row.ticket+1;seed.physical=seed.committed=row.position+1;
 m.epoch=row.epoch;m.request=row.request;m.id=row.id;m.parent=row.parent;m.position=row.position;m.token=row.token;
 m.fixture=row.fixture;m.flags=row.tentative?ring_next::wire::tentative:0;m.payload_sha=ring_next::wire::digest({});
 m.before=row.before;m.after=row.after;m.owner=0;m.publication_ticket=row.ticket;
 auto& final=out.final;final.stage=2;final.published_sequence=in.parent.commit_sequence;final.hidden=in.parent;
 final.hidden.stages=3;final.hidden.final_stage=2;auto& p=final.row;
 p.epoch=row.epoch;p.request=row.request;p.id=row.parent;p.parent=row.parent-1;p.position=row.position-1;
 p.token=in.parent.input_token;p.fixture=previous.fixture;p.owner=2;p.final=1;p.publication_ticket=in.parent.row_ticket;
 p.payload_sha=ring_next::wire::digest({});p.before=previous.id?previous.before:ring_next::request_prefix(row.request,row.epoch);p.after=row.before;
 return out;
}
void runtime_roundtrip(const std::filesystem::path& root,bool normalize_fixture,bool capture=false){
 namespace w=provider_only::wire;LoopOptions options;options.output=root;options.provider_capture_ready=capture;
 options.provider_seed_shared=root/"loop-seed";options.provider_final_shared=root/"loop-final";
 LoopEngine engine;LoopRuntime runtime;runtime.limit=5;
 std::vector<uint8_t> shared(w::shared_bytes),seed(w::shared_bytes),final(w::shared_bytes);
 auto write=[&](const auto& path,const auto& bytes){std::ofstream file(path,std::ios::binary);file.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());};
 write(options.provider_seed_shared,seed);write(options.provider_final_shared,final);
 Fixture fixture;std::vector<Witness> witnesses;std::vector<w::Request> requests;
 for(int position=1;position<=5;++position){
  auto input=fixture.next(position>=3);input.seed.fixture=position>=3?position-1:0;
  witnesses.push_back(later_witness(input,fixture.last));
  if(position>=3)witnesses.back().seed.physical+=2; // independent target may have completed pending rows
  auto& request=requests.emplace_back();
  request.op=w::batch_op;request.token=input.seed.token;request.position=position;request.fixture=input.seed.fixture;request.depth=3;request.sequence=position;
  fixture.provider.canonical(input.seed.token,position,input.head,input.hidden);fixture.last=input.seed;
 }
 for(int op:{w::dump_op,w::finish_op}){auto& request=requests.emplace_back();request.op=op;request.sequence=int(requests.size());}
 if(normalize_fixture)requests[2].fixture=1;
 size_t received=0;std::vector<w::Reply> replies;std::vector<ring_next::wire::ProposalMetaV2> proposals;
 pipeline::transport=[&](void* bytes,size_t size,bool send){
  if(send){assert(size==sizeof(w::Reply));w::Reply reply;std::memcpy(&reply,bytes,size);replies.push_back(reply);
   if(reply.status==recursive_provider::capture_ready_status){
    assert(capture&&reply.bytes==128&&reply.sequence>0&&reply.sequence<=5);
    assert(runtime.canonical_calls==reply.sequence-1); // after admit, before arithmetic
    recursive_provider::CaptureReady ready;std::memcpy(&ready,shared.data()+w::capture_offset,sizeof ready);
    const auto& source=witnesses[reply.sequence-1];auto context=fixture.context;context.stages=3;
    const auto expected=recursive_provider::captured(context,recursive_provider::seed_row(source.seed,context),source.final,reply.sequence,reply.sequence);
    assert(!std::memcmp(&ready,&expected,sizeof ready));
    // Simulate final/seed live shared slots being overwritten after capture.
    // The complete transaction must continue solely from its owned snapshots.
    std::fill(seed.begin(),seed.end(),0);std::fill(final.begin(),final.end(),0);
    write(options.provider_seed_shared,seed);write(options.provider_final_shared,final);
   }
   if(reply.bytes==sizeof(ring_next::wire::ProposalMetaV2)){ring_next::wire::ProposalMetaV2 proposal;std::memcpy(&proposal,shared.data()+w::proposal_offset,sizeof proposal);proposals.push_back(proposal);}return;}
  assert(size==sizeof(w::Request)&&received<requests.size());
  if(received<witnesses.size()){const auto& source=witnesses[received];
   std::memcpy(seed.data()+recursive_provider::seed_record_offset,&source.seed,sizeof source.seed);
   std::memcpy(final.data()+recursive_provider::final_record_offset,&source.final,sizeof source.final);
   std::memcpy(final.data()+live_draft::hidden_offset,source.hidden.data(),source.hidden.size());
   write(options.provider_seed_shared,seed);write(options.provider_final_shared,final);
  }
  std::memcpy(bytes,&requests[received++],size);
 };
 if(normalize_fixture){refusal([&]{provider_only::run_loop(engine,runtime,options,shared.data());});assert(runtime.canonical_calls==2&&replies.size()==size_t(capture?5:3));}
 else{
  provider_only::run_loop(engine,runtime,options,shared.data());
  assert(received==7&&replies.size()==size_t(capture?13:8)&&proposals.size()==5&&runtime.position()==5&&runtime.canonical_calls==5);
  assert(runtime.captures==2&&runtime.restores==2&&runtime.recursive_calls==3); // depths3,2,1
  for(const auto& reply:replies){assert(reply.rank==-1&&reply.role==w::magic&&reply.version_==1&&!reply.error);}
  assert(replies[0].bytes==16&&replies[0].sequence==0&&!replies[0].status);
  for(int i=1;i<=5;++i){
   const auto& done=replies[capture?2*i:i];assert(done.sequence==i&&!done.status&&done.bytes==224);
   if(capture){const auto& ack=replies[2*i-1];assert(ack.sequence==i&&ack.status==2&&ack.token==-1&&ack.bytes==128);}
  }
  const auto& dump=replies[replies.size()-2];const auto& finish=replies.back();
  assert(dump.sequence==6&&!dump.status&&dump.bytes==0&&finish.sequence==7&&!finish.status&&finish.bytes==0&&finish.token==-1);
  for(int i=0;i<5;++i){const auto& proposal=proposals[i];assert(proposal.base.provider_serial==uint64_t(i+1)&&proposal.base.restored_position==i+1);
   assert(proposal.base.available_depth==(i<2?0:5-i)&&proposal.base.flags==uint32_t(i<2?2:3));
   assert((i==2||proposal.guess2==-1));if(i==2)assert(proposal.guess2>=0);
  }
  assert(runtime.dumps==std::vector<std::filesystem::path>({root/"provider-dump-6",root/"provider-finish-7"}));
 }
 pipeline::transport={};
}
void canonical_no_capture(const std::filesystem::path& root){
 namespace w=provider_only::wire;LoopOptions options;options.output=root;options.provider_capture_ready=true;
 options.provider_seed_shared=root/"canonical-seed";options.provider_final_shared=root/"canonical-final";
 Fixture fixture;auto source=witness(fixture,3,false);std::vector<uint8_t> seed(w::shared_bytes),final(w::shared_bytes),shared(w::shared_bytes);
 std::memcpy(seed.data()+recursive_provider::seed_record_offset,&source.seed,sizeof source.seed);
 std::memcpy(final.data()+recursive_provider::final_record_offset,&source.final,sizeof source.final);
 std::memcpy(final.data()+live_draft::hidden_offset,source.hidden.data(),source.hidden.size());
 auto write=[](const auto& path,const auto& bytes){std::ofstream file(path,std::ios::binary);file.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());};
 write(options.provider_seed_shared,seed);write(options.provider_final_shared,final);
 LoopEngine engine;LoopRuntime runtime;int sent=0,received=0;
 pipeline::transport=[&](void* bytes,size_t size,bool send){
  if(send){assert(size==sizeof(w::Reply));w::Reply reply;std::memcpy(&reply,bytes,size);
   assert(!reply.status&&reply.sequence==sent&&reply.bytes==(sent==0?16:0));++sent;return;}
  assert(size==sizeof(w::Request));w::Request request;request.sequence=++received;
  if(received==1){request.op=w::canonical_op;request.token=source.seed.row.token;request.position=1;}
  else{assert(received==2);request.op=w::finish_op;}
  std::memcpy(bytes,&request,size);
 };
 provider_only::run_loop(engine,runtime,options,shared.data());pipeline::transport={};
 assert(sent==3&&received==2&&runtime.canonical_calls==1&&!runtime.captures&&runtime.dumps.size()==1);
}
void old_wire_main(){
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
 canonical_no_capture(root);
 runtime_roundtrip(root,false);runtime_roundtrip(root,true);
 runtime_roundtrip(root,false,true);runtime_roundtrip(root,true,true);
 {Fixture fixture;LoopRuntime runtime;auto context=fixture.context;context.stages=3;
 provider_only::Owner<LoopRuntime> owner(runtime,{{"a","b","c"},"d"},context);auto source=witness(fixture,3);
 int callbacks=0;refusal([&]{owner.run(1,source.seed,source.final,source.hidden,true,[&](const auto&,uint64_t){++callbacks;throw std::runtime_error("capture channel failed");});});
 assert(callbacks==1&&owner.failed()&&!runtime.canonical_calls);
 refusal([&]{owner.run(2,source.seed,source.final,source.hidden,true);});assert(!runtime.canonical_calls);}

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
 std::cout<<"PASS optional capture ACK before arithmetic, oneACK per command, owned source overwrite survival, callback failure poison; actual run_loop later fixture2/3/4 accepted-tentative with independent pending target rows, canonical head mask, depth3/2/1 rollback, dump+FINISH ACK; role admission and readonly source inode refusal\n";
}

void bulk_roundtrip(int bad){
 namespace b=provider_only::bulk;namespace w=provider_only::wire;
 char pattern[]="/dev/shm/dedicated-four-slot-v1-test-XXXXXX";auto root=std::filesystem::path(::mkdtemp(pattern));assert(!root.empty());
 LoopOptions options;options.output=root;options.prefill_rows=4;options.provider_seed_shared=root/"seed";options.provider_final_shared=root/"final";options.provider_prefill_seed_shared=root/"seedprefill";options.provider_prefill_final_shared=root/"finalprefill";options.provider_prefill_prompt=root/"prompt";
 std::vector<int32_t> tokens{7,10,13,16,19,22,25,28,31,34,37};options.provider_prefill_prompt_sha256=b::hex(b::digest_bytes(tokens.data(),tokens.size()*4));
 auto write=[](const auto& path,const auto* data,size_t bytes){std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(data),bytes);};
 write(options.provider_prefill_prompt,tokens.data(),tokens.size()*4);std::vector<uint8_t> shared(w::shared_bytes),journal(w::shared_bytes);write(options.provider_seed_shared,journal.data(),journal.size());write(options.provider_final_shared,journal.data(),journal.size());
 std::vector<uint8_t> seed(::pipeline::prefill::bytes(4,16)),final(seed.size());
 ::pipeline::prefill::Header h{::pipeline::prefill::magic,::pipeline::prefill::version,4,16,{}};std::memcpy(seed.data(),&h,sizeof h);std::memcpy(final.data(),&h,sizeof h);write(options.provider_prefill_seed_shared,seed.data(),seed.size());write(options.provider_prefill_final_shared,final.data(),final.size());
 LoopEngine engine;LoopRuntime runtime;runtime.limit=32;
 ring_next::wire::Context context{0,{},0,3,16,128,3};b::Prompt prompt(options.provider_prefill_prompt,options.provider_prefill_prompt_sha256,context);
 if(!bad)runtime.prefill_hook=[&]{std::fill(final.begin()+4096,final.end(),0);write(options.provider_prefill_final_shared,final.data(),final.size());};
 int requests=0,replies=0;bool ready=false;
 ::pipeline::transport=[&](void* bytes,size_t size,bool send){
  if(send){assert(size==64);const auto& reply=*static_cast<w::Reply*>(bytes);if(!ready){ready=true;return;}++replies;
   if(replies<=3){assert(reply.bytes==256&&reply.token==-1);b::Ack ack;std::memcpy(&ack,shared.data()+b::ack_offset,sizeof ack);assert(ack.sequence==uint32_t(replies)&&ack.serial==uint64_t(std::min(9,replies*4))&&ack.next_seed==ack.serial+1&&ack.flags==1);
    if(replies==3){write(root/"ack-3.bin",&ack,sizeof ack);write(root/"reply-3.bin",bytes,size);write(root/"seed-record-3.bin",seed.data()+b::record_offset,sizeof(b::Record));write(root/"final-record-3.bin",final.data()+b::record_offset,sizeof(b::Record));}
   }
   return;
  }
  assert(size==32);w::Request request;request.sequence=++requests;
  if(requests<=3){int start=(requests-1)*4,count=std::min(4,9-start),parity=(requests-1)%2;request.op=28;request.token=count;request.position=start;request.fixture=parity;
   auto* raw=final.data()+4096+(2+parity)*4*16;std::fill_n(raw,count*16,42);
   auto a=b::make(context,prompt,4,requests,start,count,parity,1,tokens.data()+start,raw),z=b::make(context,prompt,4,requests,start,count,parity,2,nullptr,raw);
   if(bad==1)a.tokens[2]^=1;
   if(bad==2)z.zero[0]=1;
   if(bad==3)z.lookahead=7;
   if(bad==4)z.raw_sha[0]^=1;
   if(bad==5)a.parity^=1;
   if(bad==6)a.role=2;
   if(bad==7)a.after[0]^=1;
   if(bad==8)a.tokens[255]=1;
   if(bad==9)h.rows=3;
b::publish(seed.data(),a);b::publish(final.data(),z);write(options.provider_prefill_seed_shared,seed.data(),seed.size());write(options.provider_prefill_final_shared,final.data(),final.size());
  }else if(requests==4){
   Fixture f;f.context=context;f.provider.state=runtime.state;f.last.epoch=0;f.last.request=context.request;f.last.id=10;f.last.parent=9;f.last.position=9;f.last.token=tokens[9];f.last.before=prompt.prefix(9);f.last.after=prompt.prefix(10);
   auto input=f.next(true);input.seed.token=tokens[10];input.seed.after=ring_next::extend(input.seed.before,10,tokens[10]);input.parent.stages=3;input.parent.final_stage=2;
   auto witness=later_witness(input,f.last);std::memcpy(journal.data()+recursive_provider::seed_record_offset,&witness.seed,sizeof witness.seed);write(options.provider_seed_shared,journal.data(),journal.size());
   std::fill(journal.begin(),journal.end(),0);std::memcpy(journal.data()+recursive_provider::final_record_offset,&witness.final,sizeof witness.final);std::copy(witness.hidden.begin(),witness.hidden.end(),journal.begin()+live_draft::hidden_offset);write(options.provider_final_shared,journal.data(),journal.size());
   request.op=27;request.token=input.seed.token;request.position=10;request.fixture=1;request.depth=3;
  }else request.op=requests==5?4:5;
  std::memcpy(bytes,&request,sizeof request);
 };
 bool failed=false;try{provider_only::run_loop(engine,runtime,options,shared.data());}catch(const std::exception&){failed=true;}
 if(bad){assert(failed&&runtime.canonical_calls==0&&replies==0);}else{assert(!failed&&runtime.position()==10&&runtime.canonical_calls==10&&runtime.captures==1&&runtime.restores==1&&replies==6);std::ifstream f(root/"provider-prefill-pairs.jsonl");std::string line;int n=0;while(std::getline(f,line))++n;assert(n==9);}
}
void original_bulk_main(){old_wire_main();bulk_roundtrip(0);for(int bad=1;bad<=8;++bad)bulk_roundtrip(bad);std::cout<<"PASS actual OP28 run_loop threechunks/partialtail, rawsource journals, exact ACK/native pairtrace/nohead, malformedtoken before arithmetic, dump+FINISH; CPU only\n";}

// New four-slot coverage. Source prepared only: compilation is deferred to root.
void four_slot_roundtrip(int bad){
 namespace b=provider_only::bulk;namespace w=provider_only::wire;namespace pf=::pipeline::prefill;
 char pattern[]="/dev/shm/provider-four-slot-test-XXXXXX";auto root=std::filesystem::path(::mkdtemp(pattern));assert(!root.empty());
 LoopOptions options;options.output=root;options.prefill_rows=256;options.prefill_slots=4;
 options.provider_seed_shared=root/"seed";options.provider_final_shared=root/"final";
 options.provider_prefill_seed_shared=root/"seedprefill";options.provider_prefill_final_shared=root/"finalprefill";options.provider_prefill_prompt=root/"prompt";
 auto write=[](const auto& path,const auto* data,size_t bytes){std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(data),bytes);};
 std::vector<int32_t> tokens(2307);for(size_t i=0;i<tokens.size();++i)tokens[i]=int(i%120);
 options.provider_prefill_prompt_sha256=b::hex(b::digest_bytes(tokens.data(),tokens.size()*4));write(options.provider_prefill_prompt,tokens.data(),tokens.size()*4);
 std::vector<uint8_t> shared(w::shared_bytes),journal(w::shared_bytes);write(options.provider_seed_shared,journal.data(),journal.size());write(options.provider_final_shared,journal.data(),journal.size());
 std::vector<uint8_t> seed(pf::bytes(256,16,4)),final(seed.size());pf::HeaderV2 h{pf::magic,2,256,16,8192,4,0,0,{}};
 std::memcpy(seed.data(),&h,sizeof h);std::memcpy(final.data(),&h,sizeof h);
 if(bad==6)reinterpret_cast<pf::HeaderV2*>(final.data())->slots=2;
 write(options.provider_prefill_seed_shared,seed.data(),seed.size());write(options.provider_prefill_final_shared,final.data(),final.size()-(bad==7?1:0));
 LoopEngine engine;LoopRuntime runtime;runtime.limit=4096;ring_next::wire::Context context{0,{},0,3,16,128,3};b::Prompt prompt(options.provider_prefill_prompt,options.provider_prefill_prompt_sha256,context);
 int requests=0,replies=0;bool ready=false;
 ::pipeline::transport=[&](void* bytes,size_t size,bool send){
  if(send){assert(size==64);const auto& reply=*static_cast<w::Reply*>(bytes);if(!ready){ready=true;return;}++replies;
   if(replies<=10){b::Ack ack;std::memcpy(&ack,shared.data()+b::ack_offset,sizeof ack);assert(reply.bytes==256&&ack.version_==2&&ack.reserved0==4&&!ack.reserved1&&ack.parity==uint32_t((replies-1)%4)&&ack.serial==uint64_t(std::min(2305,replies*256))&&ack.next_seed==ack.serial+1);}
   return;
  }
  assert(size==32);w::Request request;request.sequence=++requests;
  if(requests<=10){int start=(requests-1)*256,count=std::min(256,2305-start),slot=(requests-1)%4;
   request.op=28;request.token=count;request.position=start;request.fixture=slot;
   auto* raw=pf::reverse(final.data(),slot,256,16,4);std::fill_n(raw,count*16,42);
   auto a=b::make(context,prompt,256,requests,start,count,slot,1,tokens.data()+start,raw,4),z=b::make(context,prompt,256,requests,start,count,slot,2,nullptr,raw,4);
   if(bad==1)a.version_=1;if(bad==2)a.reserved=0;if(bad==3)request.fixture=4;
   if(bad==4)z.raw_sha[0]^=1;if(bad==5)a.parity=(slot+1)%4;
   b::publish(seed.data(),a);b::publish(final.data(),z);
   write(options.provider_prefill_seed_shared,seed.data(),seed.size());write(options.provider_prefill_final_shared,final.data(),final.size());
  }else request.op=requests==11?4:5;
  std::memcpy(bytes,&request,sizeof request);
 };
 bool failed=false;try{provider_only::run_loop(engine,runtime,options,shared.data());}catch(const std::exception&){failed=true;}
 if(bad)assert(failed&&runtime.canonical_calls==0&&replies==0);
 else {assert(!failed&&runtime.canonical_calls==2305&&runtime.position()==2305&&replies==12);std::ifstream f(root/"provider-prefill-pairs.jsonl");std::string line;int n=0;while(std::getline(f,line))++n;assert(n==2305);}
 ::pipeline::transport={};std::filesystem::remove_all(root);
}
int main(){original_bulk_main();four_slot_roundtrip(0);for(int bad=1;bad<=7;++bad)four_slot_roundtrip(bad);std::cout<<"PASS four-slot native owned source replay,10chunks/two wraps/partialtail,V2ACK/records,version/slot/extent refusal; CPU only\n";}
