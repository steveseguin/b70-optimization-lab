#pragma once
// Included after the runtime ownership types. Partition admission uses the
// actual pre-provider device census, not names or a presumed allocation order.
namespace pipeline {
struct OperatorStatePartition {
 bool enabled=false;
 std::vector<Allocation> target_device,draft_device,draft_pinned,draft_private;
};
template<class Owner> OperatorStatePartition admit_operator_partition(
 Owner& e,const std::set<Allocation>& before,const std::vector<Allocation>& draft,const std::vector<Allocation>& pinned,const std::vector<Allocation>& private_ids={}){
 require(e.a.pipeline_live_draft&&e.a.pipeline_provider()&&e.a.mtp,"operator partition live owner");
 require(!before.empty()&&!draft.empty()&&pinned.size()==2,"operator partition complete inventories");
 std::set<Allocation> declared(draft.begin(),draft.end()),private_set(private_ids.begin(),private_ids.end()),actual;
 require(private_set.size()==private_ids.size(),"duplicate provider-private ownership");
 for(auto id:private_ids){const auto& row=e.dev(0).arena.row(id);require(!declared.count(id)&&!before.count(id)&&e.allocations.count(id)&&row.live&&row.memory==Memory::device&&row.category==Category::runtime_overhead&&row.label=="card0:draft:recursive-private-image", "invalid provider-private image ownership");}
 require(private_ids.size()<=1,"bounded provider-private image count");
 require(declared.size()==draft.size(),"duplicate provider device ownership");
 OperatorStatePartition result;result.enabled=true;
 for(auto id:before){require(e.allocations.count(id)&&!declared.count(id)&&!private_set.count(id),"provider aliases preexisting target allocation");}
 for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
  require(owner.first==0&&row.live&&row.memory==Memory::device,"operator partition device census");
  if(row.category==Category::weights){require(!declared.count(id)&&!private_set.count(id),"provider mutable declaration contains weight");continue;}
  if(before.count(id))result.target_device.push_back(id);else {actual.insert(id);if(private_set.count(id))result.draft_private.push_back(id);else result.draft_device.push_back(id);}
 }
 auto complete=declared;complete.insert(private_set.begin(),private_set.end());
 require(actual==complete,"provider mutable inventory incomplete or unknown allocation");
 std::set<Allocation> unique;
 for(auto id:pinned){const auto& row=e.dev(0).arena.row(id);
  require(unique.insert(id).second&&!e.allocations.count(id)&&row.live&&row.memory==Memory::pinned,"operator pinned ownership");
  result.draft_pinned.push_back(id);
 }
 return result;
}
}
