#pragma once
#include <exception>
#include <cstdint>
#include <vector>
#include <utility>
#include <type_traits>
#include <stdexcept>
// Include after the exact pinned p58 Cache declaration. These wrappers do not
// replace Cache policy; they record each successful actual transition before
// any caller-side allocation, logging or evidence publication can throw.
namespace p213 {
static_assert(std::is_nothrow_move_constructible_v<p58::Plan>);
static_assert(std::is_nothrow_move_assignable_v<p58::Plan>);
class CacheTransition {
public:
 enum class Phase {idle,readers,ready,updating,closed};
private:
 Phase phase_=Phase::idle;uint64_t epoch_=0;bool poisoned_=false;std::exception_ptr failure_;
 static void require(bool value,const char* text){if(!value)throw std::invalid_argument(text);}
 void after_begin(uint64_t epoch)noexcept{epoch_=epoch;phase_=Phase::readers;}
 void after_finish()noexcept{phase_=Phase::ready;}
 void after_prepare()noexcept{phase_=Phase::updating;}
 void after_commit()noexcept{phase_=Phase::idle;}
 void intake()const{require(!poisoned_&&phase_!=Phase::closed,"p213 poisoned/closed cache intake");}
public:
 Phase phase()const noexcept{return phase_;}
 uint64_t epoch()const noexcept{return epoch_;}
 bool poisoned()const noexcept{return poisoned_;}
 std::exception_ptr failure()const noexcept{return failure_;}
 bool successful_close()const noexcept{return phase_==Phase::closed&&!poisoned_;}
 void poison(std::exception_ptr error=std::current_exception())noexcept{poisoned_=true;if(!failure_&&error)failure_=std::move(error);}
 uint64_t begin(p58::Cache& cache){try{intake();require(phase_==Phase::idle,"p213 begin phase");auto epoch=cache.begin_position();after_begin(epoch);return epoch;}catch(...){poison();throw;}}
 void finish(p58::Cache& cache,uint64_t epoch,bool complete){try{intake();require(phase_==Phase::readers&&epoch==epoch_,"p213 finish phase/epoch");cache.finish_position(epoch,complete);after_finish();}catch(...){poison();throw;}}
 p58::Plan prepare(p58::Cache& cache,const std::vector<uint32_t>& routes){try{intake();require(phase_==Phase::idle||phase_==Phase::ready,"p213 prepare phase");auto plan=cache.prepare(routes);after_prepare();return plan;}catch(...){poison();throw;}}
 void commit(p58::Cache& cache,uint64_t epoch,bool copies_complete,bool publication_complete){try{intake();require(phase_==Phase::updating&&epoch==epoch_,"p213 commit phase/epoch");cache.commit(epoch,copies_complete,publication_complete);after_commit();}catch(...){poison();throw;}}
 // Close never reopens intake or erases the original error. Callers must prove
 // actual owner completion before passing true; false does not touch Cache.
 bool close(p58::Cache& cache,bool drained){if(!drained)return false;if(phase_==Phase::closed)return true;try{
  if(phase_==Phase::readers){cache.finish_position(epoch_,true);after_finish();}
  if(phase_==Phase::updating)cache.close_failed(true);else cache.close();phase_=Phase::closed;return true;}catch(...){poison();throw;}
 }
};
} // namespace p213
