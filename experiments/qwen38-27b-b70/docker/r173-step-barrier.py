# R173 diagnostic: full device synchronization at the start of every execute_model call (on top of R171).
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py"
s = open(p).read()
old = "            self.synchronize_input_prep(),\n"
assert s.count(old) == 1
new = "            self._r173_step_barrier(),\n            self.synchronize_input_prep(),\n"
s = s.replace(old, new)
anchor = "    @contextmanager\n    def synchronize_input_prep(self):\n"
assert s.count(anchor) == 1
s = s.replace(anchor, """    @contextmanager
    def _r173_step_barrier(self):
        # R173: rule out cross-step device overlap as the phantom-token cause.
        torch.accelerator.synchronize()
        yield

""" + anchor)
open(p, "w").write(s)
print("R173 barrier inserted")
