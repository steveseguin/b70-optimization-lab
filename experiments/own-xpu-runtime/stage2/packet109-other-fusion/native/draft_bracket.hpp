// Included in DraftRuntime's public section. All state was reset first.
 void bracket_reset_metadata(){
  require(!async_pending,"bracket pending draft");e.drain();
  pending_head=false;pending_confirmed=0;pending_start={};reverse_hidden=nullptr;
  publication_event=0;position=0;context_extent=32;
  prepared.clear();issue_sites.clear();captured=false;
  for(const auto& l:p.launches)
   if(l.op!="gemv"&&l.op!="routed_gemv"&&l.op!="expert_gate_up")prepared.emplace(&l,bind(l));
  prepare_commands();
 }
