// Included inside Engine. Same capture and bank traversal as pipeline::banks,
// but all allocations already exist and each pair keeps its admitted extent.
void p141_reprepare_after_release() {
 drain();
 require(!dev(0).before_compute&&!dev(0).after_compute,"p141 refresh with observer");
 const int parity=bank_parity,active=active_bank,spare=spare_bank;
 if(miss_banks()) {
  require(bank_cache_ready,"p141 bank cache not initialized");
  // Suppress cross-pair extent synchronization while rebuilding each cached
  // pair at its own existing extent. No model state or selection is changed.
  bank_cache_ready=false;
  for(int i=0;i<6;++i) {
   prepare_commands();
   if(i%2==0)rotate_spare_bank();else swap_state_banks();
  }
  require(active_bank==active&&spare_bank==spare,"p141 refresh bank cycle");
  bank_cache_ready=true;
 }else {
  prepare_commands();
  if(!state_spares.empty()) {swap_state_banks();prepare_commands();swap_state_banks();}
 }
 bank_parity=parity;
}
