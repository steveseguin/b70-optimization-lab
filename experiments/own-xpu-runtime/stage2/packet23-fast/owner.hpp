#pragma once
#include "../../stage1/packet3-prep/src/owner.hpp"
namespace ownrt {
Allocation parameters(Device&,const void*,size_t,int card=0);
void* submission_parameters(const void*,size_t);
Receipt snapshot(Device&,std::string error = {});
void unregister_borrower(Device&,const std::string&);
void register_borrower(Device&,std::string);
}
