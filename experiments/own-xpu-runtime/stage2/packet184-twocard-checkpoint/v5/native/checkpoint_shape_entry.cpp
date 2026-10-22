// packet184 production-shape checkpoint rehearsal fixture (CPU only; generated mock of the REAL v5
// main.cpp/mtp.hpp/rank.hpp: numerical device addresses, no device memory, no model payload).
// One process = one rank, exactly as on device:
//   fresh   RANK OUT N                                   startup -> request reset -> admit N -> capture
//   save    RANK OUT CKPT N PENDING                      startup -> boundary controls -> engine inventory
//                                                       + draft dump -> ckpt184::stage (real)
//   restore RANK OUT CKPT INPUT MAX_NEW TOKENIZER        startup -> request reset -> verify -> apply ->
//                                                       capture -> one real half step at N (rank 1: draft
//                                                       step first) on the restored engine
// The startup sequence is run_rank's (initialize, p105 head runtime, banks/prepare, p149 probe,
// SpeculativeImage, DraftRuntime on rank 1) with the bundle-8 selection and dispatch.
#include <cxxabi.h>
#define main packet184_unexecuted_model_entry
#include "main.cpp"
#undef main
static const fs::path P184_PACKET=P184_PACKET_PATH;

static size_t p184_empty_commands=0;
static std::string capture(const Engine& e,const mtp36::DraftRuntime* draft) {
 std::vector<uint8_t> bytes;p184_empty_commands=0;
 auto add=[&](const auto& sites){for(const auto& site:sites)for(const auto& cmd:site.commands){
  if(cmd.operation_bytes.empty())++p184_empty_commands;   // counted into the digest (re-captured QSA sites after admission)
  for(auto id:cmd.ids)ownrt::arguments::append(bytes,id);
  bytes.insert(bytes.end(),cmd.operation_bytes.begin(),cmd.operation_bytes.end());
 }};
 if(e.miss_banks()){
  for(int a=0;a<3;++a)for(int b=0;b<3;++b)if(a!=b){
   const auto& c=e.bank_cache.at(a*3+b);const bool current=a==e.active_bank&&b==e.spare_bank;
   require(current||c.ready,"bank capture");
   ownrt::arguments::append(bytes,a);ownrt::arguments::append(bytes,b);ownrt::arguments::append(bytes,current?e.context_extent:c.extent);
   add(current?e.issue_sites:c.sites);
  }
 } else {add(e.issue_sites);add(e.alternate_issue_sites);ownrt::arguments::append(bytes,e.context_extent);}
 ownrt::arguments::append(bytes,e.alternate_context_extent);
 ownrt::arguments::append(bytes,e.active_bank);ownrt::arguments::append(bytes,e.spare_bank);ownrt::arguments::append(bytes,e.bank_parity);
 ownrt::arguments::append(bytes,p184_empty_commands);
 std::string out=hash(bytes);if(draft)out+="+"+draft->p184_capture_digest();return out;
}
struct Loaded {
 std::unique_ptr<Options> a;std::unique_ptr<Weights> w;std::unique_ptr<Engine> e;std::unique_ptr<p105::Runtime> head;
 std::optional<p149::Exchange> probe;std::unique_ptr<pipeline::SpeculativeImage> image;std::unique_ptr<mtp36::DraftRuntime> draft;
 std::vector<uint8_t> shared;
 ~Loaded(){draft.reset();image.reset();probe.reset();head.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}w.reset();}
};
static std::unique_ptr<Loaded> startup(int rank,const fs::path& out) {
 auto L=std::make_unique<Loaded>();L->a=std::make_unique<Options>();auto& a=*L->a;
 a.context=4096;a.cards=1;a.card=0;a.rank=rank;a.draft_rank=1;a.target_split=0;a.mtp=rank==1;a.memory="resident";
 a.gemv="r5";a.nongemv="parallel";a.timing="token";a.retain_steps.parse("none");a.seconds=600;a.wait_seconds=600;
 a.argument_audit=true;   // records operation bytes for the capture digests and re-checks every prepared argument block at issue (packet183 fixture precedent)
 a.selection=P184_PACKET/"v5/lineage/production/selection.json";
 {std::ifstream f(a.selection,std::ios::binary);std::vector<uint8_t> b((std::istreambuf_iterator<char>(f)),{});a.selection_sha256=hash(b);}
 a.dispatch=P184_PACKET/"v5/lineage/production/dispatch-speed6.json";
 const fs::path suite=P184_PACKET/"lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/incident-retrospective";
 a.plan=suite/"plan.tsv";a.auth=suite/"identity.tsv";a.draft_manifest=P184_PACKET/"mtp-manifest.tsv";a.output=out;
 fs::create_directories(out);
 packet26::dispatch.load(a.dispatch.string());
 L->w=std::make_unique<Weights>(a);auto p=pipeline::split(plan(*L->w,a),rank,false,1,0);
 require(p.g.h==2560&&p.g.context==4096&&p.g.vocab==248320,"real production dimensions");
 L->e=std::make_unique<Engine>(*L->w,a,p);L->e->initialize();
 if(L->e->split_head())L->head=std::make_unique<p105::Runtime>(*L->e);
 if(rank==0)pipeline::banks(*L->e);else{L->e->prepare_plan();L->e->prepare_commands();}
 L->shared.assign(pipeline::shared_bytes,0);
 L->probe.emplace(*L->e,L->shared.data());   // production geometry, as run_rank
 L->image=std::make_unique<pipeline::SpeculativeImage>(*L->e);
 if(a.mtp)L->draft=std::make_unique<mtp36::DraftRuntime>(*L->e);
 save(out/"census.json",L->e->dev(0).arena.census());
 return L;
}
static void reset(Loaded& L,const fs::path& out) {
 const fs::path meta=out/"reset.txt";save(meta,(out/"request").string()+"\n\n");
 pipeline::Candidate c;int accepted=0;pipeline::request_reset(*L.e,c,L.draft.get(),meta,accepted);
}
static std::string json_str(const std::string& s){return ownrt::quote(s);}
static int fresh(int rank,const fs::path& out,int N) {
 auto L=startup(rank,out);reset(*L,out);L->e->admit_position(N);
 const auto cap=capture(*L->e,L->draft.get());
 save(out/"result.json","{\"passed\":true,\"mode\":\"fresh\",\"rank\":"+std::to_string(rank)+",\"position\":"+std::to_string(N)+",\"capture\":"+json_str(cap)+
   ",\"owned_bytes\":"+std::to_string(L->e->owned_bytes[0])+",\"allocations\":"+std::to_string(L->e->allocations.size())+"}");
 return 0;
}
#ifndef P184_PARENT
static int save_mode(int rank,const fs::path& out,const fs::path& ckpt,int N,int pending) {
 auto L=startup(rank,out);auto& e=*L->e;
 // Boundary controls exactly as at the end of a real request on this rank (values only; no payload).
 const auto token_bytes=pipeline::ckpt184::read_file(ckpt/"tokens.bin");require(token_bytes.size()==size_t(N)*4,"fixture tokens.bin");
 std::vector<int> tokens(static_cast<size_t>(N),0);std::memcpy(tokens.data(),token_bytes.data(),token_bytes.size());
 const auto [h0,h1]=pipeline::ckpt184::history_of(tokens,e.p.g.eos);
 int32_t position=N,zero=0,last=tokens.back(),next=pending;
 e.put(0,"position",&position,4);e.put(0,"error",&zero,4);e.put(0,"token",&last,4);
 if(rank==1)e.put(0,"next_token",&next,4);
 if(rank==0){int64_t h[2]={h0,h1};e.put(0,"token_history",h,16);e.history0=h0;e.history1=h1;}
 if(L->draft){auto v=L->draft->checkpoint_view();int32_t dp=N-1;e.upload(0,v.buffers->at("position").id,0,&dp,4);L->draft->checkpoint_restore_host(N-1,false);}
 // The engine's own inventory at this boundary: request_state_inventory (real), state_dump's
 // enumeration (plan buffers + "alternate:" spares) and the draft runtime's dump_all_state (real).
 L->image->boundary();
 pipeline::request_state_inventory(e);
 {std::ostringstream o;o<<"[";bool comma=false;for(const auto& [name,s]:e.buffers[0]){o<<(comma?",":"")<<json_str(name);comma=true;}
  for(const auto& [name,id]:e.state_spares){o<<","<<json_str("alternate:"+name);}o<<"]";save(out/"state-labels.json",o.str());}
 if(L->draft)L->draft->dump_all_state(out/"draft-final-state");
 const fs::path request=out/"stage-request.txt";
 save(request,"dir\t"+ckpt.string()+"\nposition\t"+std::to_string(N)+"\npending\t"+std::to_string(pending)+"\n");
 const auto s=pipeline::ckpt184::stage(e,L->draft.get(),request);
 std::ostringstream o;o.precision(17);
 o<<"{\"passed\":true,\"mode\":\"save\",\"rank\":"<<rank<<",\"bytes\":"<<s.bytes<<",\"blobs\":"<<s.blobs<<",\"stage_seconds\":"<<s.seconds
  <<",\"coverage\":"<<s.coverage<<",\"host_fields\":"<<s.host_fields<<",\"capture\":"<<json_str(capture(e,L->draft.get()))<<"}";
 save(out/"result.json",o.str());return 0;
}
static int restore_mode(int rank,const fs::path& out,const fs::path& ckpt,const fs::path& input,int max_new,const fs::path& tokenizer) {
 auto L=startup(rank,out);auto& e=*L->e;reset(*L,out);
 require(e.integer(0,"position")==0,"restore requires the request reset first");
 const fs::path request=out/"restore-request.txt";
 save(request,"dir\t"+ckpt.string()+"\ntokenizer_identity\t"+tokenizer.string()+"\nmax_new\t"+std::to_string(max_new)+"\ninput\t"+input.string()+"\n");
 pipeline::ckpt184::PendingRestore pending;
 L->image->boundary();const auto verify=pipeline::ckpt184::verify_restore(e,L->draft.get(),request,pending);
 const int64_t N=pending.position;
 const auto apply=pipeline::ckpt184::apply_restore(e,L->draft.get(),pending);
 const auto cap=capture(e,L->draft.get());
 // Continue: one real step at position N on the restored engine (rank 1: the draft step first, as
 // the resumed controller issues it), through the prepared production commands (mock compute).
 int pending_token=0;{std::ifstream f(input);std::vector<int> v;int x;while(f>>x)v.push_back(x);
  const auto m=pipeline::ckpt184::parse_json(pipeline::ckpt184::read_text(ckpt/"manifest.json"));
  pending_token=int(pipeline::ckpt184::integer(pipeline::ckpt184::at(pipeline::ckpt184::at(m,"token_state"),"next_token"),"next_token"));}
 int draft_token=-1;
 if(L->draft)draft_token=L->draft->run(pending_token,int(N),true);
 pipeline::Candidate c;pipeline::Request r{pipeline::half,pending_token,int(N),0,0,1,{0,0}};
 const unsigned parity_before=e.bank_parity;
 auto reply=pipeline::half_step(e,c,r,L->shared.data(),*L->image,false);
 require(c.pending&&!c.cancelled,"continue half did not complete");
 if(rank==0)require(e.bank_parity!=parity_before,"continue half did not swap the recurrent banks");
 c={};
 std::ostringstream o;o.precision(17);
 o<<"{\"passed\":true,\"mode\":\"restore\",\"rank\":"<<rank<<",\"verify\":"<<verify<<",\"apply\":"<<apply<<",\"capture\":"<<json_str(cap)
  <<",\"continue\":{\"position\":"<<N<<",\"token\":"<<pending_token<<",\"draft_step\":"<<(L->draft?"true":"false")<<",\"draft_token\":"<<draft_token
  <<",\"half_launches_issued\":"<<reply.reserved[1]<<",\"bank_parity_before\":"<<parity_before<<",\"bank_parity_after\":"<<e.bank_parity<<"}}";
 save(out/"result.json",o.str());return 0;
}
#endif
int main(int argc,char** argv) {
 try {
  require(argc>=5,"mode rank out ...");const std::string mode=argv[1];const int rank=std::stoi(argv[2]);const fs::path out=argv[3];
  require(rank==0||rank==1,"rank");
  if(mode=="fresh"){require(argc==5,"fresh RANK OUT N");return fresh(rank,out,std::stoi(argv[4]));}
#ifndef P184_PARENT
  if(mode=="save"){require(argc==7,"save RANK OUT CKPT N PENDING");return save_mode(rank,out,argv[4],std::stoi(argv[5]),std::stoi(argv[6]));}
  if(mode=="restore"){require(argc==8,"restore RANK OUT CKPT INPUT MAX_NEW TOKENIZER");return restore_mode(rank,out,argv[4],argv[5],std::stoi(argv[6]),argv[7]);}
#endif
  throw std::runtime_error("unknown mode "+mode);
 } catch(const std::exception& x){std::cerr<<x.what()<<'\n';return 1;}
}
