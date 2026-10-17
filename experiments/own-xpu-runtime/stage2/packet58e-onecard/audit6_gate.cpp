// Includes a hash-recorded copy of production code with only payload/backend seams.
#define main unused_model_main
#include "audit6-main.cpp"
#undef main
int main(int argc,char**argv) {
 try {
  require(argc==6,"context draft_rank rank window output");
  Options a;a.context=std::stoi(argv[1]);a.draft_rank=std::stoi(argv[2]);a.rank=std::stoi(argv[3]);
  std::string window=argv[4];a.output=argv[5];fs::create_directories(a.output);
  a.memory="resident";a.cards=1;a.mtp=window!="WSs";a.plan=AUDIT6_PLAN;
  a.draft_manifest=AUDIT6_MANIFEST;
  if(window=="KD")a.draft_capture="metadata-only";
  packet26::dispatch.load(AUDIT6_DISPATCH);
  Weights w(a);auto full=plan(w,a);auto p=window=="KD"?pipeline::split(full,1,false):pipeline::split(full,a.rank,false,a.draft_rank);
  Engine e(w,a,p);e.initialize();
  if(window=="KD")e.prepare_plan();
  else if(a.rank==0)pipeline::banks(e);else {e.prepare_plan();e.prepare_commands();}
  std::unique_ptr<pipeline::SpeculativeImage> image;
  if(window!="KD")image=std::make_unique<pipeline::SpeculativeImage>(e);
  std::unique_ptr<mtp36::DraftRuntime> draft;
  if(window=="KD"||(a.mtp&&a.rank==a.draft_rank))draft=std::make_unique<mtp36::DraftRuntime>(e);
  std::array<uint8_t,pipeline::shared_bytes> shared{};
  unsigned positions=0;
  for(int position:{0,31,32,a.context-2,a.context-1}) {
   if(window!="KD") {
    e.put(0,"position",&position,4);e.admit_position(position);
    if(a.rank==0){image->begin(shared.data());image->restore();image->begin(shared.data());image->accept();image->boundary();}
    // Actual production broadcast copies and maximum retained-layer offsets.
    for(const auto& l:e.p.launches)if(l.op=="broadcast")e.execute_site(l);
    ownrt::CopyEngine copy(e.dev(0));
    for(unsigned layer=0;layer<48;++layer)e.tail=copy.copy(e.snapshots[0],size_t(layer)*4*p.g.h*2,e.buffers[0].at("streams").id,0,4*p.g.h*2,{});
    e.tail=copy.copy(e.slab[0],0,e.buffers[0].at("error").id,0,4,{});
    e.tail=copy.copy(e.slab[0],4,e.buffers[0].at("next_token").id,0,4,{});e.drain();
   }
   if(draft) {
    draft->audit_position(position);
    if(a.rank==0&&window!="KD")draft->set_reverse_hidden(shared.data());
    require(draft->begin(0,position+1,true),"async draft begin");
    if(window!="KD")draft->queue_half_inputs(0,shared.data());
    require(draft->poll_result().has_value(),"async draft completion");e.drain();
   }
   ++positions;
  }
  size_t reset_written=0;
  if(window!="KD"){pipeline::Candidate candidate;auto meta=a.output/"reset-metadata.txt";save(meta,(a.output/"reset").string()+"\n\n");auto before=audit_payload_bytes;pipeline::request_reset(e,candidate,draft.get(),meta,128);reset_written=audit_payload_bytes-before;}
  else {draft->dump(a.output/"draft-dump",true);draft->dump_all_state(a.output/"draft-state");draft->reset_request(a.output);}
  if(window!="KD") {
   bool refused=false;try{e.admit_position(a.context);}catch(const std::exception&){refused=true;}require(refused,"context overflow admitted");
  }
  // All state readback extents, including 256 MiB scratch, use actual chunking.
  for(const auto& [id,owner]:e.allocations)if(e.dev(0).arena.row(id).category!=Category::weights)e.readback(0,id,e.dev(0).arena.row(id).bytes);
  save(a.output/"census.json",e.dev(0).arena.census());
  auto* trace=Host::current;

  std::cout<<"{\"passed\":true,\"context\":"<<a.context<<",\"draft_rank\":"<<a.draft_rank<<",\"rank\":"<<a.rank<<",\"window\":"<<ownrt::quote(window)<<",\"peak_device_bytes\":"<<e.peak_device_bytes<<",\"copies\":"<<trace->copies<<",\"maximum_copy\":"<<trace->maximum<<",\"positions\":"<<positions<<",\"reset_written_bytes\":"<<reset_written<<",\"device_executed\":false}\n";
  draft.reset();image.reset();e.shutdown();
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
