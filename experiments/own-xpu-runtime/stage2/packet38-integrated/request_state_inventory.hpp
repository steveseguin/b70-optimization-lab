#pragma once
// Request-boundary evidence only; raw scratch is hashed, never retained on disk.
namespace pipeline {
static void request_state_inventory(Engine& e) {
 e.drain();require(e.pending.empty()&&!e.tail,"request inventory requires quiescence");
 std::set<Allocation> represented;
 for(const auto& card:e.buffers)for(const auto& [name,slot]:card)represented.insert(slot.id);
 for(const auto& [name,id]:e.state_spares)represented.insert(id);
 std::ostringstream out;out<<"{\"standalone_target_mutable\":{";bool comma=false;
 for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
  if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab||represented.count(id)||row.label.find(":draft:")!=std::string::npos)continue;
  auto raw=e.readback(owner.first,id,row.bytes);
  out<<(comma?",":"")<<ownrt::quote(row.label)<<":{\"bytes\":"<<row.bytes<<",\"sha256\":"<<ownrt::quote(hash(raw))<<"}";comma=true;
 }
 out<<"},\"lookup_ids_sha256\":{";comma=false;
 for(const auto& [name,bytes]:e.lookup_ids){out<<(comma?",":"")<<ownrt::quote(name)<<":"<<ownrt::quote(hash(bytes));comma=true;}
 out<<"},\"selected\":[";
 for(size_t card=0;card<e.selected.size();++card){out<<(card?",":"")<<"[";for(size_t k=0;k<e.selected[card].size();++k)out<<(k?",":"")<<e.selected[card][k];out<<"]";}
 out<<"],\"loaded_layer\":[";for(size_t card=0;card<e.loaded_layer.size();++card)out<<(card?",":"")<<e.loaded_layer[card];
 out<<"],\"fp32_cache\":[";for(size_t card=0;card<e.fp32_sources.size();++card){out<<(card?",":"")<<"{\"source\":"<<(e.fp32_sources[card]?ownrt::quote(e.dev(card).arena.row(e.fp32_sources[card]).label):"null")<<",\"extent\":"<<e.fp32_extents[card]<<"}";}
 out<<"],\"bank_parity\":"<<e.bank_parity<<",\"logical_event\":"<<e.logical
    <<",\"history0\":"<<e.history0<<",\"history1\":"<<e.history1<<",\"poisoned\":"<<(e.poisoned?"true":"false")<<"}";
 save(e.a.output/"request-state-inventory.json",out.str());
}
}
