#pragma once
#include "../../stage1/packet3-prep/src/owner.hpp"
namespace ownrt {
struct SubmissionCounts { uint64_t device_copies=0, host_waits=0, launches=0, byte_move_launches=0; uint64_t device_copies_by_card[2]{}; };
SubmissionCounts submission_counts(Device&);
extern thread_local bool preparing_parameters;
extern thread_local bool copy_is_device_to_device;
void freeze_parameters(Device&,bool);

Allocation parameters(Device&,const void*,size_t,int card=0);
void* submission_parameters(const void*,size_t);
Receipt snapshot(Device&,std::string error = {});
void unregister_borrower(Device&,const std::string&);
void register_borrower(Device&,std::string);
}
