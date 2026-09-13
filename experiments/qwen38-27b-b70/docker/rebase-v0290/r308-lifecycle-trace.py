#!/usr/bin/env python3
"""Diagnostic-only acceptance lifecycle trace layered on r308-acceptance-trace."""
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '/opt/venv/lib/python3.12/site-packages')
p=root/'vllm/v1/worker/gpu_model_runner.py'
s=p.read_text()
def edit(old,new):
 global s
 assert s.count(old)==1,(old,s.count(old))
 s=s.replace(old,new)
edit('''                "accepted_cpu_valid": accepted.tolist(),
''','''                "async_scheduling": self.use_async_scheduling,
                "async_spec_decode": self.use_async_spec_decode,
                "mamba_cache_mode": self.cache_config.mamba_cache_mode,
                "accepted_event_exists": self.num_accepted_tokens_event is not None,
                "input_batch_accepted_cpu": self.input_batch.num_accepted_tokens_cpu[:num_reqs].tolist(),
                "accepted_cpu_valid": accepted.tolist(),
''')
edit('''        for req_id in unscheduled_req_ids:
            self.input_batch.remove_request(req_id)
''','''        for req_id in unscheduled_req_ids:
            if self._gdn_state_handoff_enabled():
                if self.num_accepted_tokens_event is not None:
                    self.num_accepted_tokens_event.synchronize()
                _idx = self.input_batch.req_id_to_index[req_id]
                print("R308_TRACE_REMOVE", {
                    "req_id": req_id, "index": _idx,
                    "accepted_cpu": int(self.input_batch.num_accepted_tokens_cpu[_idx]),
                    "accepted_gpu": self.num_accepted_tokens.gpu[_idx].item(),
                    "prev_mapping": self.input_batch.prev_req_id_to_index,
                    "valid_counts": self._get_valid_sampled_token_count(),
                    "computed": self.requests[req_id].num_computed_tokens,
                    "prev_draft_len": self.requests[req_id].prev_num_draft_len,
                    "resumed": req_id in resumed_req_ids,
                    "scheduled": dict(scheduler_output.num_scheduled_tokens),
                }, flush=True)
            self.input_batch.remove_request(req_id)
''')
edit('''        for request in reqs_to_add:
            self.input_batch.add_request(request)
''','''        for request in reqs_to_add:
            self.input_batch.add_request(request)
            if self._gdn_state_handoff_enabled() and request.num_computed_tokens > 0:
                _idx = self.input_batch.req_id_to_index[request.req_id]
                print("R308_TRACE_READD", {
                    "req_id": request.req_id, "index": _idx,
                    "computed": request.num_computed_tokens,
                    "accepted_cpu": int(self.input_batch.num_accepted_tokens_cpu[_idx]),
                    "prev_draft_len": request.prev_num_draft_len,
                    "resumed": request.req_id in resumed_req_ids,
                }, flush=True)
''')
edit('''        self.num_accepted_tokens.gpu[:num_reqs] = (output_token_ids != -1).sum(dim=1)
''','''        self.num_accepted_tokens.gpu[:num_reqs] = (output_token_ids != -1).sum(dim=1)
        if bool((self.input_batch.num_computed_tokens_cpu[:num_reqs] >= 250).any()):
            print("R308_TRACE_ACCEPTED_AFTER", {
                "req_ids": list(self.input_batch.req_ids[:num_reqs]),
                "computed": self.input_batch.num_computed_tokens_cpu[:num_reqs].tolist(),
                "sampled_ids": output_token_ids.tolist(),
                "accepted_gpu": self.num_accepted_tokens.gpu[:num_reqs].tolist(),
                "async_scheduling": self.use_async_scheduling,
                "mamba_cache_mode": self.cache_config.mamba_cache_mode,
            }, flush=True)
''')
compile(s,str(p),'exec');p.write_text(s)
print('R308 lifecycle trace installed')
