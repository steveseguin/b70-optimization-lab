#include "packed.hpp"
// Linked/inspected only: no native invocation or device construction permitted.
extern "C" __attribute__((used,noinline)) integrated::Launch gsq_future_packed_submit(ownrt::Device&d,const integrated::Matrix&m,bool per_slot){return gsqn::submit(d,m,per_slot?gsqn::InputMode::per_slot:gsqn::InputMode::shared,gsqn::Storage::packed_direct);}
int main(){return 64;}
