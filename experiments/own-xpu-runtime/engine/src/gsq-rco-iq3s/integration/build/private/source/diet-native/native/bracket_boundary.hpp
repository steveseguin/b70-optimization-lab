// Included after request_reset; command 13 is accepted only at a quiescent boundary.
namespace pipeline {
static void bracket_boundary(Engine& e,Candidate& candidate,mtp36::DraftRuntime* provider,
                             SpeculativeImage& image,const fs::path& metadata,int& accepted) {
 require(!candidate.pending&&!e.progress_pending,"bracket unresolved target/draft work");
 require(!provider||!provider->submitting(),"bracket draft publication pending");
 image.boundary();e.drain();
 require(!e.poisoned&&!e.integer(0,"error"),"bracket cannot erase target error");
 if(provider)provider->flush_depth_probe();
 std::ifstream input(metadata);std::string selection,digest,reset_file,receipt;
 require(bool(std::getline(input,selection))&&bool(std::getline(input,digest))&&
         bool(std::getline(input,reset_file))&&bool(std::getline(input,receipt)),"bracket metadata");
 require(fs::path(selection).is_absolute()&&fs::path(reset_file).is_absolute()&&fs::path(receipt).is_absolute(),"bracket absolute paths");
 const auto arena=e.bracket_arena_hash(),weights=e.bracket_arena_hash(true);
 e.bracket_select(selection,digest,true);
 // Retain completed state with its old selection and physical bank roles.
 request_reset(e,candidate,provider,reset_file,accepted);accepted=0;
 e.bracket_select(selection,digest);
 // request_reset covers KV, both recurrent banks, speculative backup, scratch,
 // draft mutable allocations and host histories. Also reset capture metadata.
 if(provider)provider->bracket_reset_metadata();
 std::fill(e.loaded_layer.begin(),e.loaded_layer.end(),-1);
 e.retirement_ms=e.profiling_ms=0;e.retirement_calls=0;
 e.attribution.events.clear();e.progress_callback={};e.progress_pending=false;
 for(auto slab:e.slab){auto& row=e.dev(0).arena.row(slab);std::memset(row.pointer,0,row.bytes);}
 for(auto* staging:e.kio_host)std::memset(staging,0,e.kio_bytes); // packet188 kernel-io staging (k3 storage only)
 require(e.lookup_ids.empty()&&e.history0==e.p.g.eos&&e.history1==e.p.g.eos&&
         e.bank_parity==0&&e.context_extent==32&&e.alternate_context_extent==32,"bracket host reset incomplete");
 require(arena==e.bracket_arena_hash()&&weights==e.bracket_arena_hash(true),"bracket loaded arena identity changed");
 save(receipt,"{\"schema\":\"own-runtime.bracket.boundary.v1\",\"passed\":true,\"cached_tokens\":0,\"total_reset\":true,\"selection_sha256\":"+ownrt::quote(digest)+
      ",\"arena_descriptors_sha256\":"+ownrt::quote(arena)+",\"weight_descriptors_sha256\":"+ownrt::quote(weights)+",\"allocation_ids_preserved\":true,\"weight_uploads_after_load\":0}");
}
}
