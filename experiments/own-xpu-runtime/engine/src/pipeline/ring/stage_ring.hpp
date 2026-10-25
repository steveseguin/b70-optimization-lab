#pragma once
// Opt-in two-slot ring ledger; default wavefront and legacy paths are separate.
#include <array>
#include <algorithm>
#include <cstdint>
#include <deque>
#include <optional>
#include <limits>
#include <openssl/sha.h>
#include <stdexcept>
#include <utility>
#include <vector>
namespace ownrt::ring_next {
inline void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
using Digest=std::array<uint8_t,32>;
inline Digest extend(const Digest& before,uint32_t position,uint32_t token){
 constexpr char domain[]="ownrt.ring-prefix.v1";
 std::array<uint8_t,sizeof(domain)+32+8> raw{};std::copy_n(reinterpret_cast<const uint8_t*>(domain),sizeof(domain),raw.begin());
 std::copy(before.begin(),before.end(),raw.begin()+sizeof(domain));
 for(unsigned i=0;i<4;++i){raw[sizeof(domain)+32+i]=uint8_t(position>>(i*8));raw[sizeof(domain)+36+i]=uint8_t(token>>(i*8));}
 Digest result{};SHA256(raw.data(),raw.size(),result.data());return result;
}
inline Digest request_prefix(const Digest& request,uint64_t epoch){
 constexpr char domain[]="ownrt.ring-request.v1";std::array<uint8_t,sizeof(domain)+32+8> raw{};
 std::copy_n(reinterpret_cast<const uint8_t*>(domain),sizeof(domain),raw.begin());std::copy(request.begin(),request.end(),raw.begin()+sizeof(domain));
 for(unsigned i=0;i<8;++i)raw[sizeof(domain)+32+i]=uint8_t(epoch>>(8*i));Digest out{};SHA256(raw.data(),raw.size(),out.data());return out;
}
struct Row {
 uint64_t epoch=0,id=0,parent=0;int ticket=0,position=0,token=0,fixture=0;bool tentative=false;
 Digest request{},before{},after{};
 bool operator==(const Row&)const=default;
};
struct Resolution {int physical=0,committed=0,pending=0;std::vector<uint64_t> discarded;};
// Backend contract: exactly one synchronous device owner. Result owns immutable
// row output and Candidate metadata. Checkpoint slots are preallocated together.
// No result/slot is borrowed after ACCEPT/ABORT/reset returns.
template<class Backend> class StageRing {
 Backend& backend;bool final_,partitioned_,poisoned_=false;
 int context_,vocab_,committed_=0,last_fixture_=0,last_sequence_=0,last_output_=-1;
 uint64_t epoch_,last_id_=0,accepted_id_=0;
 Digest request_,accepted_prefix_;std::optional<Row> accepted_row_;
 struct Pending {Row row;int slot=-1;typename Backend::Result result;};
 std::deque<Pending> pending_;
 void healthy(){need(!poisoned_&&!backend.error(),"ring sticky/partial failure");backend.quiescent();}
 void sequence(int n)const{need(n>last_sequence_,"ring stale command sequence");}
 Pending& oldest(const Row& row){need(!pending_.empty()&&pending_.front().row==row,"ring oldest exact ticket/lineage required");return pending_.front();}
 template<class F>auto mutate(int sequence,F&& fn){last_sequence_=sequence;try{return fn();}catch(...){poisoned_=true;throw;}}
 Resolution receipt(std::vector<uint64_t> discarded={})const{return {backend.position(),committed_,int(pending_.size()),std::move(discarded)};}
public:
 uint64_t rows=0,tentative_rows=0,commits=0,accepted_tentative_rows=0,abort_count=0,discarded_rows=0;size_t max_pending=0;
 StageRing(Backend& b,bool final_stage,bool explicit_partition,int context,int vocab,uint64_t epoch,Digest request,Digest initial_prefix,int starting_sequence=0)
  :backend(b),final_(final_stage),partitioned_(explicit_partition),context_(context),vocab_(vocab),last_sequence_(starting_sequence),epoch_(epoch),request_(request),accepted_prefix_(initial_prefix){
  need(context>0&&vocab>0&&starting_sequence>=0&&backend.position()==0,"ring geometry/cold admission");
  need(backend.retention_disabled(),"ring requires retain_steps none");healthy();
 }
 int committed()const{return committed_;}int physical()const{return backend.position();}size_t pending()const{return pending_.size();}
 uint64_t accepted_id()const{return accepted_id_;}int last_sequence()const{return last_sequence_;}
 const typename Backend::Result& execute(const Row& row){
  healthy();sequence(row.ticket);
  need(row.epoch==epoch_&&row.request==request_&&row.id>last_id_,"ring stale request/global row identity");
  need(row.position==backend.position()&&row.position>=0&&row.position<context_&&row.token>=0&&row.token<vocab_,"ring physical position/token bounds");
  const auto parent=pending_.empty()?accepted_id_:pending_.back().row.id;
  const auto prefix=pending_.empty()?accepted_prefix_:pending_.back().row.after;
  const int prior_fixture=pending_.empty()?last_fixture_:pending_.back().row.fixture;
  need(row.parent==parent&&row.before==prefix&&row.after==extend(prefix,uint32_t(row.position),uint32_t(row.token)),"ring causal parent/prefix mismatch");
  need(row.fixture>=0&&(prior_fixture?row.fixture==prior_fixture+1:(row.fixture==0||row.fixture==1)),"ring fixture sequence");
  need(pending_.size()<2,"ring two completed-row capacity");
  need(pending_.empty()||(row.tentative&&std::all_of(pending_.begin(),pending_.end(),[](const auto& p){return p.row.tentative;})),"ring unresolved verified predecessor");
  need(!final_||(!row.tentative&&pending_.empty()),"ring final stage must verify each input");
  if(final_&&last_output_>=0)need(row.token==last_output_,"ring final input differs from committed target output");
  mutate(row.ticket,[&]{
   const int slot=row.tentative?backend.capture(row): -1;
   need(!row.tentative||(slot>=0&&slot<2),"ring checkpoint slot bound");
   if(slot>=0)for(const auto& p:pending_)need(p.slot!=slot,"ring checkpoint overwrite");
   auto result=backend.execute(row);
   need(backend.position()==row.position+1&&!backend.error(),"ring physical row completion");
   need((final_&&row.fixture>0)?result.token>=0&&result.token<vocab_:result.token==-1,"ring target output ownership");
   pending_.push_back({row,slot,std::move(result)});last_id_=row.id;++rows;if(row.tentative)++tentative_rows;max_pending=std::max(max_pending,pending_.size());
  });return pending_.back().result;
 }
 std::vector<Row> completed_tentative_rows()const{std::vector<Row> rows;for(const auto& p:pending_){need(p.row.tentative&&p.slot>=0,"provider borrow contains unresolved verified target row");rows.push_back(p.row);}return rows;}
 const Row& last_accepted()const{need(accepted_row_.has_value(),"ring has no accepted seed");return *accepted_row_;}
 const typename Backend::Result& oldest_result(const Row& row){return oldest(row).result;}
 Resolution accept(int command_sequence,const Row& row,int verified_token){
  healthy();sequence(command_sequence);auto& entry=oldest(row);
  need(row.position==committed_&&row.token==verified_token,"ring verified contiguous acceptance");
  const int physical_before=backend.position();
  return mutate(command_sequence,[&]{
   backend.publish(entry.result);if(entry.slot>=0)backend.release(entry.slot);
   if(final_&&row.fixture>0)last_output_=entry.result.token;
   accepted_id_=row.id;accepted_prefix_=row.after;accepted_row_=row;last_fixture_=row.fixture;++committed_;++commits;if(row.tentative)++accepted_tentative_rows;pending_.pop_front();
   need(backend.position()==physical_before,"ring ACCEPT rewound physical execution");return receipt();
  });
 }
 Resolution abort_suffix(int command_sequence,const Row& row){
  healthy();sequence(command_sequence);auto& entry=oldest(row);
  need(row.tentative&&row.position==committed_&&entry.slot>=0,"ring only unresolved tentative suffix can abort");
  for(const auto& p:pending_)need(p.row.tentative&&p.slot>=0,"ring suffix contains verified input");
  return mutate(command_sequence,[&]{
   backend.restore(entry.slot);need(backend.position()==committed_&&!backend.error(),"ring rollback cursor/error");
   std::vector<uint64_t> discarded;for(const auto& p:pending_){discarded.push_back(p.row.id);backend.release(p.slot);}pending_.clear();++abort_count;discarded_rows+=discarded.size();return receipt(std::move(discarded));
  });
 }
 template<class F>auto draft(int command_sequence,F&& operation){
  healthy();sequence(command_sequence);need(partitioned_&&!final_,"ring draft requires explicit independent partition");
  for(const auto& p:pending_)need(p.row.tentative,"ring draft cannot bypass verified publication");
  const int position=backend.position();return mutate(command_sequence,[&]{
   auto result=operation();healthy();need(backend.position()==position,"ring draft changed target position");return result;
  });
 }
 void reset(int command_sequence,uint64_t epoch,Digest request,Digest initial_prefix){
  healthy();sequence(command_sequence);need(pending_.empty()&&backend.position()==committed_,"ring reset needs canonical boundary");
  need(epoch_!=std::numeric_limits<uint64_t>::max()&&epoch==epoch_+1,"ring reset epoch must advance once without wrapping");
  mutate(command_sequence,[&]{backend.reset();need(backend.position()==0&&!backend.error(),"ring reset cold state");
   epoch_=epoch;request_=request;accepted_prefix_=initial_prefix;accepted_id_=last_id_=0;accepted_row_.reset();committed_=last_fixture_=0;last_output_=-1;rows=tentative_rows=commits=accepted_tentative_rows=abort_count=discarded_rows=0;max_pending=0;
  });
 }
 void boundary(){healthy();need(pending_.empty()&&backend.position()==committed_,"ring uncommitted boundary");}
};
}
