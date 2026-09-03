# R174 diagnostic: make CpuGpuBuffer host->device copies blocking, so a later CPU overwrite of a reused
# pinned buffer cannot race a still-queued copy (on the R156 image, no traces).
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/utils.py"
s = open(p).read()
old = """    def copy_to_gpu(self, n: int | None = None) -> torch.Tensor:
        if n is None:
            return self.gpu.copy_(self.cpu, non_blocking=True)
        return self.gpu[:n].copy_(self.cpu[:n], non_blocking=True)
"""
assert s.count(old) == 1
new = """    def copy_to_gpu(self, n: int | None = None) -> torch.Tensor:
        # R174 diagnostic: blocking H2D copies.
        if n is None:
            return self.gpu.copy_(self.cpu, non_blocking=False)
        return self.gpu[:n].copy_(self.cpu[:n], non_blocking=False)
"""
open(p, "w").write(s.replace(old, new)); print("R174 blocking copies inserted")
