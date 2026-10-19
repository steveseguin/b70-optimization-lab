#pragma once
#include "async_backend.hpp"
namespace ownrt {
struct ForegroundTails {
 Event compute=0,copy=0;
 void record(Event event,bool is_copy=false){(is_copy?copy:compute)=event;}
 void clear(){compute=copy=0;}
 template<class Complete>bool complete(Complete query)const {
  return (!compute||query(compute))&&(!copy||query(copy));
 }
};
// Packet76 adaptation: compute and foreground copy each have an in-order
// terminal. Maintenance is separately owned and is NEVER part of this proof.
struct ForegroundPrefix {
 virtual ~ForegroundPrefix()=default;
 virtual bool foreground_prefix_complete()=0;
};
void set_ordered_retirement(Device&,bool);
bool ordered_retirement(const Device&);
}
