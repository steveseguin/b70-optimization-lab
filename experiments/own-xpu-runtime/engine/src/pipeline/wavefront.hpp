#pragma once
#include <cstdint>
#include <stdexcept>
#include <optional>

// Pure state machine: no device, filesystem, model arithmetic or clock.
// A ticket is its WAVE_ROW socket sequence. This protocol has no RESET; tickets
// cannot be reused within the owner's socket lifetime.
namespace ownrt::wavefront {
constexpr int row_op=20,commit_op=21,abort_op=22;
inline void check(bool value,const char* message){if(!value)throw std::invalid_argument(message);}
struct Row {
 int ticket=0,token=0,position=0,fixture=0;bool tentative=false;
};
class Ledger {
 bool final_;int context_,vocab_,position_=0,fixture_=0,last_ticket_=0,last_output_=-1;
 std::optional<Row> pending_;
public:
 uint64_t rows=0,tentative_rows=0,commits=0,aborts=0;
 Ledger(bool final_stage,int context,int vocab):final_(final_stage),context_(context),vocab_(vocab){check(context>0&&vocab>0,"wavefront geometry");}
 bool pending()const{return pending_.has_value();}
 int position()const{return position_;}
 const Row& candidate()const{check(pending(),"wavefront missing candidate");return *pending_;}
 void begin(Row r){
  check(!pending(),"wavefront allows one unresolved row per stage");
  check(r.ticket>last_ticket_&&r.ticket>0,"wavefront stale/reused ticket");
  check(r.position==position_&&r.position>=0&&r.position<context_,"wavefront causal position");
  check(r.token>=0&&r.token<vocab_,"wavefront token bounds");
  check(r.fixture>=0&&(fixture_?r.fixture==fixture_+1:(r.fixture==0||r.fixture==1)),"wavefront fixture sequence");
  check(!r.tentative||(!final_&&r.fixture>0),"wavefront final/prompt stage cannot execute tentative input");
  if(final_&&last_output_>=0)check(r.token==last_output_,"wavefront final input differs from previous committed target output");
  pending_=r;last_ticket_=r.ticket;++rows;if(r.tentative)++tentative_rows;
 }
 void match(int ticket,int token,int position,int fixture)const{
  const auto& r=candidate();check(r.ticket==ticket&&r.token==token&&r.position==position&&r.fixture==fixture,"wavefront resolve ticket identity");
 }
 void commit(int ticket,int token,int position,int fixture,int output){
  match(ticket,token,position,fixture);
  check((final_&&fixture>0)?output>=0&&output<vocab_:output==-1,"wavefront final output ownership");
  position_=position+1;fixture_=fixture;if(final_&&fixture>0)last_output_=output;
  pending_.reset();++commits;
 }
 void abort(int ticket,int token,int position,int fixture){
  match(ticket,token,position,fixture);check(candidate().tentative,"wavefront cannot abort verified input");pending_.reset();++aborts;
 }
 void boundary()const{check(!pending(),"wavefront unresolved row at boundary");}
};
} // namespace ownrt::wavefront
