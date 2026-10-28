#pragma once
#include "pipeline/provider_only/prefill.hpp"
#include "pipeline/provider_only/reset_transaction.hpp"
#include "pipeline/recursive_provider/capture_ready.hpp"
namespace ownrt::provider_only {
inline ring_next::Digest request_digest(const std::string& text){
 ring_next::need(text.size()==64,"provider request digest extent");ring_next::Digest out{};
 auto nibble=[](char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;};
 for(size_t i=0;i<32;++i){int a=nibble(text[2*i]),b=nibble(text[2*i+1]);ring_next::need(a>=0&&b>=0,"provider request lowercase digest");out[i]=uint8_t(16*a+b);}return out;
}
// Included after rank transport declaration. No target Dispatcher/StageRing is
// constructed. The controller must retain target ACCEPT leases until reply.
template<class Engine,class Draft,class Options>
void run_loop(Engine& engine,Draft& draft,const Options& options,uint8_t* shared){
 ring_next::need(shared,"provider private shared mapping");
 ring_next::need(options.provider_replay.empty(),"provider archived replay not implemented; live witnesses required");
 ring_next::wire::Context context{0,request_digest(options.pipeline_ring_request_sha256),0,
   int(options.provider_target_bdfs.size()),int(engine.stream_bytes()),engine.p.g.vocab,options.pipeline_ring_depth};
 ring_next::wire::context(context);
 Owner<Draft> owner(draft,{options.provider_target_bdfs,options.provider_bdf},context);
 LivePeers peers(options.provider_seed_shared,options.provider_final_shared);
 std::unique_ptr<bulk::Prompt> prompt;std::unique_ptr<bulk::Peers> bulk_peers;std::ofstream bulk_trace,bulk_chunks;
 if(!options.provider_prefill_prompt.empty()){
  prompt=std::make_unique<bulk::Prompt>(options.provider_prefill_prompt,options.provider_prefill_prompt_sha256,context);
  bulk_peers=std::make_unique<bulk::Peers>(options.provider_prefill_seed_shared,options.provider_prefill_final_shared,options.prefill_rows,context.stream_bytes,options.prefill_slots);
  bulk_chunks.open(options.output/"provider-prefill-chunks.jsonl");ring_next::need(bool(bulk_chunks),"bulk native chunk trace open");
  bulk_trace.open(options.output/"provider-prefill-pairs.jsonl");ring_next::need(bool(bulk_trace),"bulk native pair trace open");
 }
 auto reset_suite=suite::Suite::startup(options,context,engine.p.g.context);
 const auto cold_path=options.output/"provider-cold-baseline";
 if(reset_suite){ring_next::need(prompt&&bulk_peers,"suite requires actual bulk provider");draft.live_dump(cold_path);}
 auto allocation_identity=[&]{
  std::ostringstream out;out<<engine.dev(0).generation()<<'\n';
  auto item=[&](auto id,int card){const auto&r=engine.dev(card).arena.row(id);ring_next::need(r.live,"provider reset dead allocation");out<<id<<' '<<card<<' '<<r.bytes<<' '<<int(r.memory)<<' '<<int(r.category)<<' '<<uintptr_t(r.pointer)<<' '<<r.label<<'\n';};
  for(const auto&[id,where]:engine.allocations)item(id,where.first);
  for(auto id:draft.live_pinned_inventory())item(id,0);
  const auto text=out.str();return bulk::hex(bulk::digest_bytes(text.data(),text.size()));
 };
 wire::Header header;header.stream_bytes=context.stream_bytes;header.target_stages=context.stages;
 header.depth=context.depth;header.request=context.request;std::memcpy(shared,&header,sizeof header);
 wire::Reply ready;ready.bytes=context.stream_bytes;::pipeline::transfer(options.channel,&ready,sizeof ready,true,options.seconds);
 int sequence=0;auto output=options.output;
 for(;;){
  wire::Request request;::pipeline::transfer(options.channel,&request,sizeof request,false,options.seconds);
  wire::command(request,++sequence);wire::Reply reply;reply.sequence=sequence;
  if(request.op==bulk::op){
   ring_next::need(prompt&&bulk_peers&&!request.depth,"bulk explicit native ownership admission");
   auto witness=bulk_peers->capture(context,*prompt,request.position,request.token,request.fixture);
   owner.prefill(sequence,*prompt,witness,[&](const auto& row,const uint8_t* hidden,size_t bytes){
    bulk_trace<<"{\"position\":"<<row.position<<",\"token\":"<<row.token<<",\"head\":false,\"provider_serial\":"<<row.position<<",\"hidden_bytes\":"<<bytes<<",\"hidden_sha256\":\""<<bulk::hex(bulk::digest_bytes(hidden,bytes))<<"\",\"command_sequence\":"<<sequence<<"}\n";ring_next::need(bool(bulk_trace),"bulk native pair trace write");
   });bulk_trace.flush();ring_next::need(bool(bulk_trace),"bulk native pair trace flush");
   bulk::Ack ack;ack.version_=::pipeline::prefill::transport_version(options.prefill_slots);ack.reserved0=options.prefill_slots==4?4:0;ack.sequence=sequence;ack.start=request.position;ack.count=request.token;ack.parity=request.fixture;ack.rows=options.prefill_rows;ack.stream_bytes=context.stream_bytes;ack.stages=context.stages;ack.seed_sequence=witness.seed.published_sequence;ack.final_sequence=witness.final.published_sequence;ack.next_seed=owner.serial()+1;ack.epoch=context.epoch;ack.serial=owner.serial();ack.request=context.request;ack.prompt_sha=prompt->sha;ack.seed_sha=bulk::digest_bytes(&witness.seed,sizeof witness.seed);ack.final_sha=bulk::digest_bytes(&witness.final,sizeof witness.final);ack.raw_sha=witness.final.raw_sha;
   bulk_chunks<<"{\"epoch\":"<<ack.epoch<<",\"request\":\""<<bulk::hex(ack.request)<<"\",\"sequence\":"<<sequence<<",\"start\":"<<ack.start<<",\"count\":"<<ack.count<<",\"serial\":"<<ack.serial<<",\"prompt_sha256\":\""<<bulk::hex(ack.prompt_sha)<<"\",\"seed_record_sha256\":\""<<bulk::hex(ack.seed_sha)<<"\",\"final_record_sha256\":\""<<bulk::hex(ack.final_sha)<<"\",\"raw_sha256\":\""<<bulk::hex(ack.raw_sha)<<"\"}\n";bulk_chunks.flush();ring_next::need(bool(bulk_chunks),"bulk native chunk trace flush");
   std::memcpy(shared+bulk::ack_offset,&ack,sizeof ack);reply.bytes=sizeof ack;
  }else if(request.op==wire::canonical_op||request.op==wire::batch_op){
   ring_next::need(request.depth==(request.op==wire::batch_op?context.depth:0),"provider requested depth");
   auto witness=peers.capture(context);auto row=recursive_provider::seed_row(witness.seed,context);
   ring_next::need(request.token==row.token&&request.position==row.position&&request.fixture==row.fixture,
      "provider command/source identity");
   if(request.op==wire::canonical_op)owner.canonical(sequence,witness.seed,witness.final,witness.hidden);
   else{
    auto proposal=owner.run(sequence,witness.seed,witness.final,witness.hidden,options.pipeline_ring_recursive_verify,
      [&](const auto& admitted,uint64_t serial){
       if(!options.provider_capture_ready)return;
       const auto captured=recursive_provider::captured(context,admitted,witness.final,sequence,serial);
       static_assert(wire::reset_offset+sizeof(wire::Reset)<=wire::capture_offset&&
         wire::capture_offset+sizeof(captured)<=wire::proposal_offset);
       std::memcpy(shared+wire::capture_offset,&captured,sizeof captured);
       wire::Reply event;event.status=recursive_provider::capture_ready_status;
       event.bytes=sizeof captured;event.sequence=sequence;
       ::pipeline::transfer(options.channel,&event,sizeof event,true,options.seconds);
      });
    if(context.depth==3){ring_next::wire::ProposalMetaV2 full;full.base=proposal;full.guess2=(owner.last_result().guesses.size()<3?-1:owner.last_result().guesses[2]);
      std::memcpy(shared+wire::proposal_offset,&full,sizeof full);reply.bytes=sizeof full;
    }else{std::memcpy(shared+wire::proposal_offset,&proposal,sizeof proposal);reply.bytes=sizeof proposal;}
    reply.token=proposal.guess0;
   }
  }else{
   ring_next::need(!request.token&&!request.position&&!request.fixture&&!request.depth,"provider control zero payload");owner.boundary();
   if(request.op==wire::reset_op){
    wire::Reset reset;std::memcpy(&reset,shared+wire::reset_offset,sizeof reset);
    ring_next::need(reset.magic_==uint32_t(wire::magic)&&reset.version_==wire::version&&reset.bytes==sizeof reset&&
      reset.sequence==uint32_t(sequence)&&std::all_of(reset.zero.begin(),reset.zero.end(),[](auto n){return !n;}),"provider reset header");
    if(reset_suite){
     const auto metadata=options.output/("reset-"+std::to_string(sequence)+".json");
     auto prepared=reset_suite->prepare(metadata,options.output,context,-1,sequence,true);
     const auto& d=prepared.descriptor;
     ring_next::need(reset.epoch==d.next_epoch&&reset.request==prepared.next.request,"provider wire/descriptor reset binding");
     output=d.destination;ring_next::need(std::filesystem::create_directories(output),"provider suite fresh output");
     std::string before,after;size_t canonical_bytes=0;
     auto zero_private=[&](auto& runtime){
      std::vector<uint8_t> zero(std::min(size_t(4*1024*1024),runtime.recursive_bytes));ring_next::need(!zero.empty(),"provider reset private extent");
      for(size_t off=0;off<runtime.recursive_bytes;off+=zero.size())engine.upload(0,runtime.recursive_image,off,zero.data(),std::min(zero.size(),runtime.recursive_bytes-off));
      engine.drain();
      for(size_t off=0;off<runtime.recursive_bytes;off+=zero.size()){
       const auto raw=engine.readback_range(0,runtime.recursive_image,off,std::min(zero.size(),runtime.recursive_bytes-off));
       ring_next::need(std::all_of(raw.begin(),raw.end(),[](uint8_t b){return !b;}),"provider private reset bytes nonzero");
      }
     };
     auto cold_check=[&]{
      // Existing sealed Writer repeated-dump verification: checks EVERY owned
      // canonical source and host metadata against the actual cold startup dump.
      // It does not rewrite/rebaseline an existing seal.
      draft.live_dump(cold_path);
      canonical_bytes=0;for(auto id:draft.live_mutable_inventory())canonical_bytes+=engine.dev(0).arena.row(id).bytes;
      for(auto id:draft.live_pinned_inventory())canonical_bytes+=engine.dev(0).arena.row(id).bytes;
      return true;
     };
     auto seal_maintenance=[&](const BulkResetEvidence& evidence){
      before=evidence.allocation_before;after=evidence.allocation_after;
      auto reopen=[&](std::ofstream& stream,const char* name){stream.close();stream.clear();stream.open(output/name);ring_next::need(bool(stream),"provider reset bulk trace open");};
      reopen(bulk_trace,"provider-prefill-pairs.jsonl");reopen(bulk_chunks,"provider-prefill-chunks.jsonl");
      std::ofstream maintenance(output/"provider-reset-maintenance.json");
      maintenance<<"{\"canonical_full_sealed_baseline_verified\":true,\"canonical_bytes\":"<<canonical_bytes<<",\"private_zero_bytes\":"<<draft.recursive_bytes<<",\"shared_invalidated_bytes\":"<<evidence.invalidated_bytes<<"}\n";
      maintenance.flush();ring_next::need(bool(maintenance),"provider reset maintenance receipt write");
     };
     reset_bulk_owner(owner,prepared,prompt,std::span<uint8_t>(shared,wire::shared_bytes),zero_private,allocation_identity,cold_check,seal_maintenance,true);
     context=prepared.next;std::memcpy(&header,shared,sizeof header);
     ring_next::need(owner.bulk_reset_ready(),"provider reset receipt before bulk readiness");
     std::ofstream receipt(output/"provider-reset.json");
     receipt<<"{\"schema\":\"ownrt.dedicated-provider-reset.v1\",\"passed\":true,\"global_sequence\":"<<sequence
      <<",\"next_epoch\":"<<context.epoch<<",\"next_request_sha256\":\""<<bulk::hex(context.request)
      <<"\",\"prompt_sha256\":\""<<d.prompt.prompt_sha<<"\",\"suite_sha256\":\""<<d.prompt.suite_sha<<"\",\"prompt_index\":"<<d.prompt.index
      <<",\"metadata_sha256\":\""<<bulk::hex(bulk::digest_bytes(d.raw.data(),d.raw.size()))<<"\",\"provider_serial\":0,\"bulk_closed\":false,\"bulk_used\":false"
      <<",\"allocation_inventory_before_sha256\":\""<<before<<"\",\"allocation_inventory_after_sha256\":\""<<after
      <<"\",\"canonical_full_sealed_baseline_verified\":true,\"canonical_bytes\":"<<canonical_bytes<<",\"private_zero_bytes\":"<<draft.recursive_bytes<<"}\n";
     receipt.flush();ring_next::need(bool(receipt),"provider final reset receipt write");
    }else{
    output=options.output/("request-"+std::to_string(reset.epoch));
    ring_next::need(std::filesystem::create_directory(output),"provider reset fresh output");
    owner.reset(sequence,reset.epoch,reset.request,output,[&](auto& runtime){
     std::vector<uint8_t> zero(std::min(size_t(4*1024*1024),runtime.recursive_bytes));
     ring_next::need(!zero.empty(),"provider private backup extent");
     for(size_t offset=0;offset<runtime.recursive_bytes;offset+=zero.size())
       engine.upload(0,runtime.recursive_image,offset,zero.data(),std::min(zero.size(),runtime.recursive_bytes-offset));
     engine.drain();
    });
    context.epoch=reset.epoch;context.request=reset.request;header.epoch=context.epoch;header.request=context.request;
    std::memcpy(shared,&header,sizeof header);
    }
   }else if(request.op==wire::dump_op){draft.live_dump(output/("provider-dump-"+std::to_string(sequence)));}
   else if(request.op==wire::finish_op){draft.live_dump(output/("provider-finish-"+std::to_string(sequence)));}
  }
  owner.boundary();::pipeline::transfer(options.channel,&reply,sizeof reply,true,options.seconds);
  if(request.op==wire::finish_op)return;
 }
}
} // namespace ownrt::provider_only
