#pragma once
// Opt-in quiescent request boundary. Included after legacy request_reset and
// checkpoint implementation; no process lifecycle or allocation replacement.
namespace pipeline {
inline std::pair<fs::path,std::string> persistent_request_spec(const fs::path& metadata,const fs::path& original){
 gsq_bundle::FD fd(::open(metadata.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC));require(fd.n>=0,"persistent metadata open");
 const auto before=gsq_bundle::stamp(fd.n);require(before.st_size>0&&before.st_size<=8192,"persistent metadata bounded extent");
 std::string text(size_t(before.st_size),'\0');size_t done=0;
 while(done<text.size()){const auto n=::pread(fd.n,text.data()+done,text.size()-done,off_t(done));if(n<0&&errno==EINTR)continue;require(n>0,"persistent metadata read");done+=size_t(n);}
 struct stat named{};require(!::lstat(metadata.c_str(),&named)&&gsq_bundle::same(before,gsq_bundle::stamp(fd.n))&&gsq_bundle::same(before,named),"persistent metadata replaced");
 const auto split=text.find('\n');require(split!=std::string::npos&&split>0&&text.find('\n',split+1)==text.size()-1&&text.find('\0')==std::string::npos&&text.find('\r')==std::string::npos,"persistent metadata exactly two lines");
 const std::string output=text.substr(0,split),oracle=text.substr(split+1,text.size()-split-2);
 fs::path destination(output);require(destination.is_absolute()&&destination==destination.lexically_normal(),"persistent reset normalized absolute destination");
 const auto owner=fs::canonical(original);const auto relative=destination.lexically_relative(owner);
 auto status=[](const fs::path& path){std::error_code error;auto value=fs::symlink_status(path,error);require(!error||error==std::errc::no_such_file_or_directory,"persistent reset path status");return value;};
 require(!relative.empty()&&relative!="."&&!relative.is_absolute()&&*relative.begin()!=".."&&status(destination).type()==fs::file_type::not_found,"persistent reset fresh owned destination");
 for(auto parent=destination.parent_path();parent!=owner;parent=parent.parent_path()){
  require(!parent.empty()&&parent!=parent.parent_path(),"persistent reset ancestry");const auto type=status(parent).type();
  require(type==fs::file_type::not_found||type==fs::file_type::directory,"persistent reset symlink parent");
 }
 return {destination,oracle};
}
inline fs::path persistent_destination(const fs::path& metadata,const fs::path& original){return persistent_request_spec(metadata,original).first;}
inline void persistent_reset(Engine& e,Candidate& candidate,mtp36::DraftRuntime* provider,
 StageCheckpoint& checkpoint,ownrt::wavefront::Ledger& ledger,ownrt::live_draft::Sequence& draft_sequence,
 const fs::path& original,const fs::path& metadata,int accepted,int sequence,uint8_t* shared,size_t bytes,
 std::ofstream& wave_trace,size_t& trace_rows,size_t& trace_omitted){
 require(e.a.pipeline_persistent_requests&&e.a.pipeline_live_draft,"persistent reset opt-in mode");
 ledger.boundary();require(!candidate.pending&&!checkpoint.active()&&(!provider||!provider->submitting()),"persistent reset unresolved owner");
 checkpoint.attest(ledger);const auto admitted=persistent_request_spec(metadata,original);const auto& destination=admitted.first;require(admitted.second==e.a.oracle.string(),"persistent reset oracle identity changed");
 if(provider){provider->live_reset_admission();require(provider->live_position()==std::max(0,e.integer(0,"position")-1),"persistent reset draft true-pair frontier");}
 if(provider&&e.a.reset_dump)provider->live_dump(e.a.output/"draft-before-reset-sealed");
 const size_t allocation_count=e.allocations.size();
 request_reset(e,candidate,provider,metadata,accepted,admitted);
 require(e.a.output==destination&&e.allocations.size()==allocation_count,"persistent reset owner allocation/output identity");
 checkpoint.reset_at_boundary();ledger=ownrt::wavefront::Ledger(e.a.pipeline_final(),e.p.g.context,e.p.g.vocab);draft_sequence=ownrt::live_draft::Sequence{};
 require(shared&&bytes>0,"persistent reset shared allocation");std::memset(shared,0,bytes);
 wave_trace.close();wave_trace.clear();wave_trace.open(destination/"wavefront.jsonl");require(bool(wave_trace),"persistent reset wavefront trace");trace_rows=trace_omitted=0;
 for(auto name:{"launch-plan.json","pipeline-stage.json","wavefront-checkpoint-layout.json"}){
  require(fs::is_regular_file(original/name),"persistent reset immutable sidecar missing");fs::copy_file(original/name,destination/name,fs::copy_options::none);
 }
 require(e.integer(0,"position")==0&&!e.integer(0,"error")&&(!provider||(provider->live_position()==0&&provider->live_extent()==32)),"persistent cold positions/error");
 // No device work follows this point. Copy-table/extent reconstruction and
 // the final state checks belong to reset maintenance, not the next request.
 e.drain();e.submission_card=-1;e.current_cls=0;e.host_waits=0;e.parity_argument_checks=0;
 e.wait_ms=e.prepare_ms=e.enqueue_ms=e.enqueue_including_wait_ms=0;e.gemv_ms=e.nongemv_ms=e.transfer_ms=0;
 e.submitted=e.max_submission_ns=0;e.retirement_ms=e.profiling_ms=0;e.retirement_calls=e.capacity_reprepares=0;
 e.correction_exchange_calls=e.correction_send_bytes=e.correction_receive_bytes=0;e.family_ms.fill(0);
 std::fill(e.class_ms.begin(),e.class_ms.end(),0);std::fill(e.class_launches.begin(),e.class_launches.end(),0);std::fill(e.class_groups.begin(),e.class_groups.end(),0);
 std::ostringstream out;out<<"{\"schema\":\"ownrt.pipeline-reset.v1\",\"passed\":true,\"stage_id\":"<<e.a.pipeline_stage
  <<",\"global_sequence\":"<<sequence<<",\"target_position\":0,\"draft_position\":"<<(provider?"0":"null")
  <<",\"pending_ticket\":false,\"sticky_error\":0,\"allocation_ids_preserved\":true,\"context_extent\":"<<e.context_extent
  <<",\"alternate_extent\":"<<e.alternate_context_extent<<",\"counters_reset\":true,\"trace_reset\":true}";
 save(destination/"wavefront-reset.json",out.str());
}
}
