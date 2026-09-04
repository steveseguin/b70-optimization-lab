# R207 diagnostic/candidate: XpuCommunicator.all_reduce without the host-side Work.wait().
# R199c: per single-user MTP1 step the GPUs run ~3.5 ms of compute in a 35 ms step; 128 all-reduces per forward each
# end in a host wait that drains the queue. If XCCL enqueues on the current XPU stream, ordering is preserved without the
# wait and outputs stay bit-identical (the strict 12/12 gate decides); if not, the gate fails and the arm is closed.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/distributed/device_communicators/xpu_communicator.py"
s = open(p).read()
old = '''    def all_reduce(self, input_: torch.Tensor) -> torch.Tensor:
        output = input_.clone()
        work = dist.all_reduce(output, group=self.device_group, async_op=True)
        work.wait()
        return output
'''
new = '''    def all_reduce(self, input_: torch.Tensor) -> torch.Tensor:
        output = input_.clone()
        work = dist.all_reduce(output, group=self.device_group, async_op=True)
        if _R207_HOST_WAIT:
            work.wait()
        return output
'''
assert s.count(old) == 1, "all_reduce anchor"
s = s.replace(old, new)
s = s.replace("import torch\n", "import torch\nimport os as _r207_os\n_R207_HOST_WAIT = _r207_os.environ.get(\"VLLM_XPU_ALLREDUCE_HOST_WAIT\", \"1\") == \"1\"\n", 1)
assert "_R207_HOST_WAIT" in s
open(p, "w").write(s)
print("R207: all_reduce host wait gated by VLLM_XPU_ALLREDUCE_HOST_WAIT (default 1 = unchanged); sha256", hashlib.sha256(s.encode()).hexdigest())
