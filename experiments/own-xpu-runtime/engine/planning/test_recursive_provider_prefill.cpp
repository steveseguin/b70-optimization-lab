#include "pipeline/recursive_provider/batch.hpp"
#include <cassert>
#include <iostream>
using namespace ownrt::ring_next;
int main(){
 Digest request{},seed=request_prefix(request,0);ownrt::ring_next::wire::Context context{0,request,0,4,16,97,2};
 ownrt::recursive_provider_next::Sequence sequence(context);
 Row first;first.epoch=0;first.request=request;first.id=2;first.parent=1;first.ticket=7;first.position=1;first.token=5;first.before=extend(seed,0,3);first.after=extend(first.before,1,5);
 sequence.prefill(first,3);assert(sequence.serial()==1);
 Row second;second.epoch=0;second.request=request;second.id=3;second.parent=2;second.ticket=9;second.position=2;second.token=8;second.before=first.after;second.after=extend(second.before,2,8);
 sequence.prefill(second,5);assert(sequence.serial()==2);
 Row bad=second;bad.id=4;bad.parent=1;bad.position=3;bad.ticket=11;bad.after=extend(bad.before,3,8);
 bool refused=false;try{sequence.prefill(bad,5);}catch(const std::exception&){refused=true;}assert(refused&&sequence.serial()==2);
 std::cout<<"PASS canonical DRAFT prefill sequence and ancestry; CPU only\n";
}
