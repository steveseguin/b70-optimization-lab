// Included in DraftRuntime's public section (session checkpoint, opt-in rank ops 17-19; lab 2026-10-26).
// A read-only view of the draft's mutable state for the checkpoint classification, and the host-field restore that
// APPLY performs after the request reset. Nothing here runs unless one of those ops is sent.
 struct CheckpointView {
  const std::map<std::string,Slot>* buffers=nullptr;const std::set<Allocation>* mutable_ids=nullptr;const flash::Plan* plan=nullptr;
  int position=0;bool disabled=false;int context_extent=0;bool pending=false,reverse_hidden=false;int queued_probe=-1;
 };
 CheckpointView checkpoint_view()const{
  return {&buffers,&mutable_ids,&p,position,disabled,context_extent,async_pending||e.progress_pending,reverse_hidden!=nullptr,queued_probe};
 }
 // After request_reset (reset_request zeroed every mutable allocation and set position 0) and after the checkpoint
 // bytes were uploaded: the draft host position/disabled flag; the QSA launch extent follows from the position exactly
 // as compute() derives it before every draft step.
 void checkpoint_restore_host(int restored_position,bool restored_disabled){
  require(!async_pending&&!e.progress_pending&&queued_probe==-1&&queued_confirmed==-1&&!reverse_hidden,"draft checkpoint restore requires a quiescent draft");
  require(position==0&&!disabled,"draft checkpoint restore requires the request reset first");
  require(restored_position>=0&&restored_position<p.g.context,"draft checkpoint restore position bound");
  position=restored_position;disabled=restored_disabled;admit_position();
 }
