#pragma once
#include <cstdint>
#include <stdexcept>
namespace p106 {
inline constexpr unsigned prefix=46336,suffix=45056,vocab=91392,hidden_bytes=5120;
struct Best {float value;int32_t index;uint32_t error,reserved;};
static_assert(sizeof(Best)==16);
inline Best merge(Best a,Best b){
 if(a.index<0||a.index>=int(prefix)||b.index<int(prefix)||b.index>=int(vocab)||a.reserved||b.reserved)
  throw std::invalid_argument("p106 invalid partition payload");
 Best out=(b.value>a.value||(b.value==a.value&&b.index<a.index))?b:a;
 out.error=a.error|b.error;return out;
}
// A per-thread scope routes only these four bounded staging copies to BCS.
// No engine/owner ABI changes and no environment switch affects other copies.
inline thread_local bool copy_bcs=false;
struct CopyScope {bool prior;explicit CopyScope(bool b):prior(copy_bcs){copy_bcs=b;}~CopyScope(){copy_bcs=prior;}};
// Dedicated reverse-slot mailbox; independent of speculative streams/draft.
struct alignas(64) Mailbox {
 alignas(4) uint32_t request=0,reply=0,abort=0;
 int32_t position=-1,fixture=-1;
 Best best{};
 alignas(64) uint8_t hidden[hidden_bytes]{};
};
inline uint32_t load(const uint32_t& x){return __atomic_load_n(&x,__ATOMIC_ACQUIRE);}
inline void publish(uint32_t& x,uint32_t v){__atomic_store_n(&x,v,__ATOMIC_RELEASE);}
}
