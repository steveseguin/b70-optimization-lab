# R180 fix candidate: make MambaManager record its newly allocated block ids for worker-side zeroing.
# R178 showed the worker-side hook alone is a no-op: SingleTypeKVCacheManager only records new block ids when its
# spec is an AttentionSpec, so scheduler_output.new_block_ids_to_zero never carries a GDN state page and R178's
# _zero_mamba_pages zeroed attention page ids (already zeroed by KVBlockZeroer) instead of the recycled GDN page.
# The raw KV tensors are shared across groups (one block id = one page in every layer view), so passing the Mamba ids
# through the same list is safe for KVBlockZeroer too.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/core/single_type_kv_cache_manager.py"
s = open(p).read()
assert hashlib.sha256(s.encode()).hexdigest() == "1a0dedb76ed07c64fa780e10a89ff718c37975804bf70594a9577c6ecebd5787", "unexpected manager file"
old = '''        self._record_new_block_ids = needs_kv_cache_zeroing and isinstance(
            kv_cache_spec, AttentionSpec
        )
'''
new = '''        # R180: Mamba/GDN state pages must be zeroed on (re)allocation too; the
        # worker (R178 _zero_mamba_pages) zeroes conv/ssm views for these ids.
        self._record_new_block_ids = needs_kv_cache_zeroing and isinstance(
            kv_cache_spec, (AttentionSpec, MambaSpec)
        )
'''
assert s.count(old) == 1, "record condition not found"
s = s.replace(old, new)
# align-mode allocation path (unused when prefix caching is off, patched for completeness)
old2 = '''                req_blocks.extend(new_blocks)
                self._allocated_block_reqs.add(request_id)
'''
new2 = '''                req_blocks.extend(new_blocks)
                if self._record_new_block_ids:  # R180
                    self.new_block_ids.extend(b.block_id for b in new_blocks)
                self._allocated_block_reqs.add(request_id)
'''
assert s.count(old2) == 1, "align-mode extend not found"
s = s.replace(old2, new2)
open(p, "w").write(s)
print("R180 mamba new-block recording inserted; sha256", hashlib.sha256(s.encode()).hexdigest())
