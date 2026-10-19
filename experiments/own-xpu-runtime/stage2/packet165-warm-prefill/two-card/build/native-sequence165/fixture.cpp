#define main unused_device_entry
#include "probe-main.cpp"
#undef main
#include "native_sequence_helpers.hpp"
// Exact reset method is extracted, byte-for-byte, from frozen mtp.hpp.
// A small facade avoids the real DraftRuntime constructor's model reads.
struct DraftResetFacade {
 Engine& e;flash::Plan p;std::set<Allocation> mutable_ids;
 Allocation publication,half_staging,active;bool async_pending=false,disabled=false;
 int position=0;const void* reverse_hidden=nullptr;ownrt::Event publication_event=0;
 std::ofstream trace;
 explicit DraftResetFacade(Engine& engine):e(engine),p(engine.p) {
  active=e.allocate(0,"cpu-draft:active",4,Category::scratch,Lifetime::transaction);
  publication=e.allocate(0,"cpu-draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned);
  half_staging=e.allocate(0,"cpu-draft:staging",4+4*p.g.h*2,Category::pinned_slab,Lifetime::transfer,Memory::pinned);
  mutable_ids.insert(active);
 }
 Allocation id(const char*){return active;}
#include "draft_reset.inc"
};
int main(int argc,char**argv){try{
 auto a=parse(argc,argv);a.output=std::getenv("ENTRY_PREPARE_OUTPUT");fs::create_directories(a.output);
 const auto root=a.output;require(!a.mini&&a.context==4096&&a.tokens==512,"production parser geometry");
 packet26::dispatch.load(a.dispatch);Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,a.mini,a.draft_rank,a.target_split);
 Engine e(w,a,p);e.deadline=std::chrono::steady_clock::time_point::max();e.initialize();pipeline::banks(e);
 pipeline::SpeculativeImage image(e);pipeline::Candidate candidate;std::vector<uint8_t> shared(pipeline::shared_bytes);
 const auto before=identities(e);size_t total=0;int index=0;
 for(const auto& id:sequence_ids()){
  auto previous=e.a.output;auto dest=root/id;auto metadata=root/("reset-"+std::to_string(index)+".txt");
  save(metadata,dest.string()+"\n\n");
  // Real rank command dispatch flushes deferred rank1 reporting before RESET.
  if(a.rank==1)e.reply_report.before(11);
  image.boundary();candidate={};const auto poisoned=poison_samples(e);
  pipeline::request_reset(e,candidate,nullptr,metadata,0);
  if(a.rank==1)e.reply_report.after(11);
  require(reset_samples(e)==poisoned,"mutable sample coverage");identity_check(e,before);total+=poisoned;
  remove_synthetic_dumps(previous);sensors(e,id);
  if(id!="after-suite")for(int pos:{0,1,511,512}){
   e.put(0,"position",&pos,4);candidate={};pipeline::Request request{pipeline::half,2,pos,pos<2?0:1,0,++index,{}};
   if(a.rank==1)e.reply_report.before(pipeline::half);
   auto reply=pipeline::half_step(e,candidate,request,shared.data(),image,false);require(!reply.error,"sticky error");
   if(a.rank==1)e.reply_report.published();
  }
  candidate={};++index;
 }
 if(a.rank==1)e.reply_report.flush();
 bool pending_refused=false;candidate.pending=true;
 try{pipeline::request_reset(e,candidate,nullptr,root/"not-opened",0);}catch(const std::exception&){pending_refused=true;}
 require(pending_refused,"pending target reset accepted");candidate={};
 bool poisoned_refused=false;e.poisoned=true;
 try{pipeline::request_reset(e,candidate,nullptr,root/"not-opened",0);}catch(const std::exception&){poisoned_refused=true;}
 require(poisoned_refused,"poisoned target reset accepted");e.poisoned=false;
 // Exercise the unchanged draft reset method separately, with its required
 // pinned publication/staging and mutable active allocation on the real owner.
 DraftResetFacade draft(e);
 const auto draft_ids=identities(e);
 for(const auto& id:sequence_ids()){
  auto dest=root/("draft-"+id);fs::create_directories(dest);
  std::memset(e.dev(0).arena.row(draft.active).pointer,0xa5,4);
  std::memset(e.dev(0).arena.row(draft.publication).pointer,0xa5,8);
  std::memset(e.dev(0).arena.row(draft.half_staging).pointer,0xa5,4+4*p.g.h*2);
  draft.position=19;draft.disabled=true;draft.reverse_hidden=&e;draft.publication_event=99;
  e.progress_pending=true;e.progress_callback=[]{};draft.reset_request(dest);
  identity_check(e,draft_ids);
  uint32_t active=0;std::memcpy(&active,e.dev(0).arena.row(draft.active).pointer,4);require(active==1,"draft active reset");
  require(!draft.position&&!draft.disabled&&!draft.reverse_hidden&&!draft.publication_event&&!e.progress_pending&&!e.progress_callback,"draft state reset");
  for(auto allocation:{draft.publication,draft.half_staging}){auto& r=e.dev(0).arena.row(allocation);for(size_t k=0;k<r.bytes;++k)require(static_cast<uint8_t*>(r.pointer)[k]==0,"draft pinned reset");}
  sensor(draft.trace,id,"draft-rows");
 }
 bool refused=false;draft.async_pending=true;try{draft.reset_request(root);}catch(const std::exception&){refused=true;}require(refused,"pending draft reset accepted");draft.async_pending=false;
 e.shutdown();std::cout<<"PASS native sequence rank="<<a.rank<<" requests=13 target_resets=14 draft_method_resets=14 pending_and_poisoned_refused=true mutable_samples="<<total<<"\n";return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
