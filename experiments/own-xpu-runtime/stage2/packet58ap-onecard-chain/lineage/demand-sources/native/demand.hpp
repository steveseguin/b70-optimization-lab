#pragma once
#include <array>
#include <cstdint>
#include <stdexcept>
#include <algorithm>
namespace p58am {
constexpr size_t gate_bytes=524800, up_bytes=524800, down_bytes=921600;
constexpr size_t expert_bytes=gate_bytes+up_bytes+down_bytes, entries=64;
constexpr size_t pool_bytes=entries*expert_bytes;
static_assert(pool_bytes==126156800);
struct Slot { uint64_t gate=0,up=0,down=0,generation=0; uint32_t expert=0,resident=0,valid=0,pad=0; };
struct Map { std::array<Slot,10> slots{}; uint64_t position=0; uint32_t layer=0,pad=0; };
enum class State:uint8_t {free,copying,retained,leased};
struct Entry { State state=State::free; uint32_t expert=0; uint64_t snapshot=0,epoch=0,ticket=0; bool consumed=false; };
// Fixed storage: later-token compute never consults this table. Only the
// unchanged cache policy may select an entry as its later fill source.
struct Pool {
 std::array<Entry,entries> rows{};
 uint64_t staged_bytes=0,unused_bytes=0,repeated_bytes=0,d2d_bytes=0;
 std::array<uint64_t,48*512/64> seen{};
 size_t high_water=0;
 int acquire(uint32_t expert,uint64_t snapshot,bool resident_neighbor,bool pending) {
  if(expert>=48*512||!resident_neighbor||pending)return -1;
  auto it=std::find_if(rows.begin(),rows.end(),[](auto& e){return e.state==State::free;});
  if(it==rows.end())return -1;
  auto mask=uint64_t(1)<<(expert%64);if(seen[expert/64]&mask)repeated_bytes+=expert_bytes;
  seen[expert/64]|=mask;*it={State::copying,expert,snapshot,0,0,false};staged_bytes+=expert_bytes;
  high_water=std::max(high_water,size_t(std::count_if(rows.begin(),rows.end(),[](auto&e){return e.state!=State::free;})));
  return int(it-rows.begin());
 }
 void copied(int i,uint64_t ticket){auto&e=rows.at(i);if(e.state!=State::copying||!ticket)throw std::logic_error("demand copy state");e.ticket=ticket;e.state=State::retained;}
 void consumed(uint64_t snapshot){for(auto&e:rows)if(e.snapshot==snapshot&&e.state!=State::free)e.consumed=true;}
 int select(uint32_t expert,uint64_t snapshot,uint64_t epoch){
  for(size_t i=0;i<rows.size();++i){auto&e=rows[i];if(e.state==State::retained&&e.expert==expert&&e.snapshot==snapshot){if(!e.consumed)throw std::logic_error("D2D before consumer completion");e.state=State::leased;e.epoch=epoch;return i;}}return -1;
 }
 int leased(uint32_t expert,uint64_t epoch)const{for(size_t i=0;i<rows.size();++i)if(rows[i].state==State::leased&&rows[i].expert==expert&&rows[i].epoch==epoch)return int(i);return -1;}
 void discard(uint64_t snapshot){for(auto&e:rows)if(e.snapshot==snapshot&&e.state==State::retained){if(!e.consumed)throw std::logic_error("discard before consumer");unused_bytes+=expert_bytes;e={};}}
 void fill_done(uint64_t epoch,bool complete){if(!complete)throw std::logic_error("D2D lease still reading");for(auto&e:rows)if(e.state==State::leased&&e.epoch==epoch){d2d_bytes+=expert_bytes;e={};}}
 void reset(bool drained){if(!drained)throw std::logic_error("demand reset with readers");for(auto&e:rows){if(e.state==State::leased)throw std::logic_error("demand reset with fill lease");e={};}seen.fill(0);}
};
// Separate demand namespace. No demand ticket enters the foreground ledger or
// replaces the maintenance terminal ticket. Backend owns every native handle.
struct Backend {
 virtual ~Backend()=default;
 virtual uint64_t demand_copy(void*,const void*,size_t,uint64_t producer)=0;
 virtual bool demand_complete(uint64_t)=0;
 virtual void demand_barrier(uint64_t)=0;
 virtual void demand_drain()=0;
 virtual size_t demand_pending()=0;
 virtual void demand_retire()=0;
 virtual std::array<uint64_t,2> demand_timing(uint64_t)=0;
};
}
