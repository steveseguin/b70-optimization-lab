#include "pipeline/live_draft.hpp"
#include <cassert>
#include <iostream>
using namespace ownrt::live_draft;
template<class F>void refusal(F f){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}assert(rejected);}
int main(){Handoff h;h.bytes=40960;h.position=0;h.final_stage=3;h.stages=4;h.row_ticket=1;h.commit_sequence=2;h.input_token=7;h.hidden_sha256.fill('a');
 validate(h,40960,4,97);Sequence s;
 s.admit(h,1,9,1,97); // final prompt pair may run draft head before target head
 s.complete(h,1);assert(s.next_position()==2);refusal([&]{s.admit(h,1,9,1,97);});
 h.position=1;h.row_ticket=3;h.commit_sequence=4;h.head=1;h.next_token=25;
 refusal([&]{s.admit(h,2,26,1,97);});s.admit(h,2,25,1,97);s.complete(h,2);
 h.commit_sequence=3;refusal([&]{validate(h,40960,4,97);});h.commit_sequence=4;h.bytes=65540;refusal([&]{validate(h,65540,4,97);});
 std::cout<<"PASS live draft typed handoff, prompt bootstrap, contiguous canonical position, stale/wrong input refusal; CPU only\n";
}
