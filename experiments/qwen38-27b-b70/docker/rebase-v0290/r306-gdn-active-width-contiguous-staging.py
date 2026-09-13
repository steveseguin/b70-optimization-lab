# R306 (2026-09-13): PR #53542's active-width staging in GDNAttentionMetadataBuilder exposes
# self.spec_state_indices_tensor[:batch_size, :active_spec_width], a NON-contiguous view of the [max_bs, num_spec+1]
# buffer whenever the active width is below the maximum. The XPU kernel requires a contiguous spec_state_indices_tensor
# ("spec_state_indices_tensor must be contiguous"), so a full decode graph captured for a scheduled K < max (the 9B
# scheduled-draft profile with the dynsd-fullgraph overlay) dies at capture. Fix: one persistent, contiguous staging
# buffer per active width, allocated at init (graph capture must not allocate), used by the staging path.
import pathlib
p = pathlib.Path("/opt/venv/lib/python3.12/site-packages/vllm/v1/attention/backends/gdn_attn.py")
s = p.read_text()
old_alloc = '''        self.spec_state_indices_tensor: torch.Tensor = torch.empty(
            (self.decode_cudagraph_max_bs, self.num_spec + 1),
            dtype=torch.int32,
            device=device,
        )
'''
new_alloc = old_alloc + '''        # R306: contiguous staging buffers per active runtime-K width (2..num_spec+1); the max-width
        # buffer is the original tensor above.
        self.spec_state_indices_by_width: dict[int, torch.Tensor] = {
            self.num_spec + 1: self.spec_state_indices_tensor
        }
        for _w in range(2, self.num_spec + 1):
            self.spec_state_indices_by_width[_w] = torch.empty(
                (self.decode_cudagraph_max_bs, _w), dtype=torch.int32, device=device
            )
'''
old_stage = '''            self.spec_state_indices_tensor[:num_spec_decodes, :active_spec_width].copy_(
                spec_state_indices_tensor, non_blocking=True
            )
            spec_state_indices_tensor = self.spec_state_indices_tensor[
                :batch_size, :active_spec_width
            ]
            spec_state_indices_tensor[num_spec_decodes:].fill_(NULL_BLOCK_ID)
'''
new_stage = '''            # R306: stage into the contiguous per-width buffer (a column slice of the max-width
            # buffer is not contiguous, and the XPU kernel rejects it).
            _staging = self.spec_state_indices_by_width[active_spec_width]
            _staging[:num_spec_decodes].copy_(spec_state_indices_tensor, non_blocking=True)
            spec_state_indices_tensor = _staging[:batch_size]
            spec_state_indices_tensor[num_spec_decodes:].fill_(NULL_BLOCK_ID)
'''
assert s.count(old_alloc) == 1 and s.count(old_stage) == 1, (s.count(old_alloc), s.count(old_stage))
s = s.replace(old_alloc, new_alloc).replace(old_stage, new_stage)
p.write_text(s)
print("R306 applied")
