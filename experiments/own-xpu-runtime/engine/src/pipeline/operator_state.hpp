#pragma once
// Included after the runtime ownership types. Partition admission uses the
// actual pre-provider device census, not names or a presumed allocation order.
namespace pipeline {
struct OperatorStatePartition {
 bool enabled=false;
 std::vector<Allocation> target_device,draft_device,draft_pinned;
};
template<class Owner> OperatorStatePartition admit_operator_partition(
 Owner& e,const std::set<Allocation>& before,const std::vector<Allocation>& draft,const std::vector<Allocation>& pinned){
 require(e.a.pipeline_live_draft&&e.a.pipeline_first()&&e.a.mtp,"operator partition live owner");
 require(!before.empty()&&!draft.empty()&&pinned.size()==2,"operator partition complete inventories");
 std::set<Allocation> declared(draft.begin(),draft.end()),actual;
 require(declared.size()==draft.size(),"duplicate provider device ownership");
 OperatorStatePartition result;result.enabled=true;
 for(auto id:before){require(e.allocations.count(id)&&!declared.count(id),"provider aliases preexisting target allocation");}
 for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
  require(owner.first==0&&row.live&&row.memory==Memory::device,"operator partition device census");
  if(row.category==Category::weights){require(!declared.count(id),"provider mutable declaration contains weight");continue;}
  if(before.count(id))result.target_device.push_back(id);else {actual.insert(id);result.draft_device.push_back(id);}
 }
 require(actual==declared,"provider mutable inventory incomplete or unknown allocation");
 std::set<Allocation> unique;
 for(auto id:pinned){const auto& row=e.dev(0).arena.row(id);
  require(unique.insert(id).second&&!e.allocations.count(id)&&row.live&&row.memory==Memory::pinned,"operator pinned ownership");
  result.draft_pinned.push_back(id);
 }
 return result;
}
}
