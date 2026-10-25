// Included inside DraftRuntime. Qualification-only host captures; no device
// allocations or provider computations occur around a target suffix restore.
struct SurvivalAllocation {
 Allocation id{};std::string label,role;size_t bytes=0;Memory memory{};std::vector<uint8_t> data;
 bool operator==(const SurvivalAllocation&)const=default;
};
struct SurvivalSnapshot {
 std::vector<SurvivalAllocation> allocations;RecursiveHost current_host,saved_host;RecursiveTarget saved_target;
 std::vector<RecursiveRow> row_metadata;int saved_class=0;uint64_t captures=0,restores=0,verified=0;size_t bytes=0,allocated=0;Allocation image{};bool active=false;
 std::string descriptors,sequence,host,payload;
};
std::string survival_host_json(const RecursiveHost& h)const{
 namespace v=ownrt::provider_survival;std::ostringstream out;out<<"{\"position\":"<<h.position<<",\"extent\":"<<h.extent<<",\"pending_confirmed\":"<<h.pending_confirmed<<",\"queued_probe\":"<<h.queued_probe<<",\"queued_confirmed\":"<<h.queued_confirmed<<",\"depth\":"<<h.depth<<",\"disabled\":"<<(h.disabled?"true":"false")<<",\"async_pending\":"<<(h.async_pending?"true":"false")<<",\"pending_head\":"<<(h.pending_head?"true":"false")<<",\"reverse_present\":"<<(h.reverse_present?"true":"false")<<",\"captured\":"<<(h.captured?"true":"false")<<",\"publication_event\":"<<h.publication_event<<",\"pending_start_ticks\":"<<h.pending_start.time_since_epoch().count()<<",\"reverse_bytes\":"<<h.reverse_bytes.size()<<",\"reverse_sha256\":"<<v::quote(v::sha(h.reverse_bytes))<<"}";return out.str();
}
std::string survival_target_digest(const RecursiveTarget& t)const{
 ownrt::provider_survival::Identity out;out.numbers(t.sources);out.numbers(t.extents);out.integer(t.lookup.size());for(const auto& [name,bytes]:t.lookup){out.text(name);out.bytes(bytes);}out.integer(t.selected.size());for(const auto& rows:t.selected)out.numbers(rows);out.numbers(t.loaded);for(auto value:{int64_t(t.history0),int64_t(t.history1),int64_t(t.parity),int64_t(t.active),int64_t(t.spare),int64_t(t.extent),int64_t(t.alternate)})out.integer(uint64_t(value));return out.digest();
}
std::string survival_binding_digest()const{
 ownrt::provider_survival::Identity out;out.text("ownrt.provider-bindings.v1");out.integer(prepared.size());
 for(const auto& [launch,item]:prepared){out.integer(reinterpret_cast<uintptr_t>(launch));out.integer(reinterpret_cast<uintptr_t>(&item));const auto& s=item.spec;
  for(auto value:{int(s.no_materialize_gather),int(s.fused_combine_norm),s.extent,s.implementation,int(s.op),int(s.special),s.ni,s.no,s.nw,int(s.packed_heads),int(s.f32_activations),s.tokens,int(s.tmp_row_bytes)})out.integer(uint64_t(value));
  const auto& g=s.g;for(auto value:{g.h,g.low,g.experts,g.top,g.mid,g.kh,g.vh,g.d,g.qh,g.kvh,g.ad,g.ih,g.id,g.rotary,g.budget,g.context,g.vocab,g.eos})out.integer(uint64_t(value));
  out.numbers(s.site.shape);out.numbers(s.site.weights);out.integer(s.site.parameter);out.numbers(s.sizes);out.numbers(s.types);out.numbers(s.grids);out.numbers(s.weight_elements);out.numbers(s.row_bytes);out.numbers(item.bindings);out.integer(reinterpret_cast<uintptr_t>(item.submit));
 }
 out.integer(issue_sites.size());for(const auto& site:issue_sites){out.integer(reinterpret_cast<uintptr_t>(&site));out.integer(site.gemv);out.integer(site.cls);out.integer(site.head);out.integer(site.commands.size());
  for(const auto& command:site.commands){out.integer(reinterpret_cast<uintptr_t>(&command));out.integer(reinterpret_cast<uintptr_t>(&command.submit));out.integer(bool(command.submit));out.numbers(command.ids);out.integer(command.pointers.size());for(auto pointer:command.pointers)out.integer(reinterpret_cast<uintptr_t>(pointer));out.integer(command.generation);out.integer(command.queue);out.integer(reinterpret_cast<uintptr_t>(command.owner));out.bytes(command.argument_bytes);out.bytes(command.operation_bytes);out.integer(reinterpret_cast<uintptr_t>(command.copy_counter));}
 }
 // The opaque submit closure retains immutable bindings and shared Device queue
 // ownership. Its stable object address/bool and all exposed typed descriptors
 // are checked; std::function storage/padding or mutable shared queue internals
 // are not serialized. Shared Device copy_counter VALUES legitimately advance.
 return out.digest();
}
SurvivalSnapshot capture_survival(const ownrt::recursive_provider_next::Sequence& sequence){
 recursive_idle();require(recursive_healthy()&&!recursive_active,"provider survival capture needs completed canonical state");recursive_inventory();
 SurvivalSnapshot s;s.current_host=recursive_host_state();s.saved_host=recursive_host;s.saved_target=recursive_target;s.row_metadata=recursive_rows;s.saved_class=recursive_class;s.captures=recursive_captures;s.restores=recursive_restores;s.verified=recursive_verified_restores;s.bytes=recursive_bytes;s.allocated=allocated;s.image=recursive_image;s.active=recursive_active;s.sequence=sequence.survival_identity();s.descriptors=survival_binding_digest();
 size_t total=0;auto read=[&](Allocation id,const std::string& role){const auto& row=e.dev(0).arena.row(id);require(row.live&&row.bytes&&row.bytes<=80ull*1024*1024&&total<=80ull*1024*1024-row.bytes,"bounded provider survival capture");total+=row.bytes;SurvivalAllocation item{id,row.label,role,row.bytes,row.memory,{}};if(row.memory==Memory::pinned){auto* p=static_cast<const uint8_t*>(row.pointer);item.data.assign(p,p+row.bytes);}else {require(row.memory==Memory::device,"provider survival memory ownership");item.data=e.readback(0,id,row.bytes);}s.allocations.push_back(std::move(item));};
 for(const auto& item:recursive_rows)read(item.id,"canonical");read(recursive_image,"recursive-image");
 namespace v=ownrt::provider_survival;v::Identity rows;rows.integer(recursive_rows.size());for(const auto& row:recursive_rows){rows.integer(row.id);rows.integer(row.bytes);rows.integer(row.offset);rows.integer(uint64_t(row.memory));rows.text(row.label);rows.bytes(row.pinned_before);}
 std::ostringstream host;host<<"{\"current\":"<<survival_host_json(s.current_host)<<",\"saved\":"<<survival_host_json(s.saved_host)<<",\"saved_target_sha256\":"<<v::quote(survival_target_digest(s.saved_target))<<",\"saved_rows_sha256\":"<<v::quote(rows.digest())<<",\"saved_class\":"<<s.saved_class<<",\"captures\":"<<s.captures<<",\"restores\":"<<s.restores<<",\"verified_restores\":"<<s.verified<<",\"private_bytes\":"<<s.bytes<<",\"allocated_bytes\":"<<s.allocated<<",\"image_id\":"<<s.image<<",\"active\":"<<(s.active?"true":"false")<<"}";s.host=host.str();
 std::ostringstream payload;payload<<"{\"schema\":\"ownrt.provider-survival-state.v1\",\"position\":"<<position<<",\"provider_serial\":"<<sequence.serial()<<",\"allocations\":[";
 for(size_t i=0;i<s.allocations.size();++i){const auto& row=s.allocations[i];payload<<(i?",":"")<<"{\"id\":"<<row.id<<",\"label\":"<<v::quote(row.label)<<",\"bytes\":"<<row.bytes<<",\"memory\":"<<v::quote(row.memory==Memory::device?"device":"pinned")<<",\"role\":"<<v::quote(row.role)<<",\"sha256\":"<<v::quote(v::sha(row.data))<<"}";}
 payload<<"],\"host\":"<<s.host<<",\"sequence\":"<<s.sequence<<",\"prepared_bindings_sha256\":"<<v::quote(s.descriptors)<<",\"excluded_shared_counter_values\":[\"Engine timing/submission totals\",\"Device copy_counter values\"]}";s.payload=payload.str();return s;
}
SurvivalSnapshot verify_survival(const SurvivalSnapshot& before,const ownrt::recursive_provider_next::Sequence& sequence){
 auto after=capture_survival(sequence);
 require(before.allocations==after.allocations,"target abort changed canonical/pinned/provider-private bytes");
 require(before.current_host==after.current_host&&before.saved_host==after.saved_host&&before.saved_target==after.saved_target&&before.row_metadata==after.row_metadata,"target abort changed provider host snapshot metadata");
 require(before.saved_class==after.saved_class&&before.captures==after.captures&&before.restores==after.restores&&before.verified==after.verified&&before.bytes==after.bytes&&before.allocated==after.allocated&&before.image==after.image&&before.active==after.active,"target abort changed provider private counters/identity");
 require(before.sequence==after.sequence&&before.descriptors==after.descriptors&&before.host==after.host&&before.payload==after.payload,"target abort changed provider Sequence/prepared bindings/state identity");return after;
}
