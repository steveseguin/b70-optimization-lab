#!/usr/bin/env python3
"""R308: retain GDN acceptance across an unscheduled request's batch eviction.

R307 fixes slot handoff but InputBatch.add_request resets accepted count to 1.
An async boundary pause after partial rejection drops the previous-row mapping;
on re-add, the live SSM/conv state is still at accepted-1. Preserve the count
before eviction, then restore only that request's current CPU/GPU runner row.
Actual preemption/resumption and finished IDs invalidate the saved count.
"""
from pathlib import Path
import sys

# Kept as one literal so GPU-free unit tests exercise the exact inserted methods.
METHODS = '''    def _r308_preserve_gdn_acceptance(self, unscheduled_req_ids, scheduler_output):
        saved = self.__dict__.setdefault("_r308_paused_gdn_acceptance", {})
        resumed = scheduler_output.scheduled_cached_reqs.resumed_req_ids
        for req_id in set(scheduler_output.finished_req_ids) | set(resumed):
            saved.pop(req_id, None)
        if not self._gdn_state_handoff_enabled() or self.cache_config.mamba_cache_mode == "align":
            return
        paused = set(unscheduled_req_ids) - set(resumed)
        if not paused:
            return
        # The previous forward's D2H accepted counts must finish before batch
        # removal/addition can reset or reuse their CPU rows.
        if self.num_accepted_tokens_event is not None:
            self.num_accepted_tokens_event.synchronize()
        for req_id in paused:
            row = self.input_batch.req_id_to_index.get(req_id)
            if row is not None:
                count = int(self.input_batch.num_accepted_tokens_cpu[row])
                if count > 1:
                    saved[req_id] = count
                else:
                    saved.pop(req_id, None)

    def _r308_restore_gdn_acceptance(self, num_reqs):
        saved = self.__dict__.get("_r308_paused_gdn_acceptance")
        if not saved:
            return
        # Called after default initialization / previous-batch GPU correction.
        # Resolve by request ID after condense/reorder; never bulk-copy stale
        # CPU counts over another row's async GPU correction.
        for row, req_id in enumerate(self.input_batch.req_ids[:num_reqs]):
            count = saved.pop(req_id, None)
            if count is not None:
                self.num_accepted_tokens.np[row] = count
                self.num_accepted_tokens.gpu[row] = count

'''

def patch(root):
    path=Path(root)/'vllm/v1/worker/gpu_model_runner.py'
    text=path.read_text()
    assert '_r308_preserve_gdn_acceptance' not in text
    def edit(old,new):
        nonlocal text
        assert text.count(old)==1,(old,text.count(old))
        text=text.replace(old,new)
    edit('''        for req_id in unscheduled_req_ids:
            self.input_batch.remove_request(req_id)
''','''        # R308: batch eviction must not discard the live GDN rollback slot.
        self._r308_preserve_gdn_acceptance(unscheduled_req_ids, scheduler_output)
        for req_id in unscheduled_req_ids:
            self.input_batch.remove_request(req_id)
''')
    edit('''        self.req_indices.np[:total_num_scheduled_tokens] = req_indices
''','''        # R308: a paused request has no previous-row mapping, but its
        # retained recurrent state still needs the pre-pause accepted count.
        self._r308_restore_gdn_acceptance(num_reqs)
        self.req_indices.np[:total_num_scheduled_tokens] = req_indices
''')
    edit('''    def _gdn_state_handoff_enabled(self) -> bool:
''',METHODS+'''    def _gdn_state_handoff_enabled(self) -> bool:
''')
    compile(text,str(path),'exec');path.write_text(text)
    print('R308 GDN state resume installed:',path)

if __name__=='__main__':
    patch(sys.argv[1] if len(sys.argv)>1 else '/opt/venv/lib/python3.12/site-packages')
