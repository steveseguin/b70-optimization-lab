// Shared by the native rank dispatch and the CPU sequence regression.
static void p141_run_probe(Engine& engine,p105::Runtime* head,int token,int position) {
 engine.p141_probe(token,position);
 // Probe scratch release invalidates every capture on rank0's Device, including
 // the split-head suffix outside Engine's recurrent-bank command caches.
 if(head)head->p141_prepare_suffix();
}
