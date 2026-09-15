# Independent source review of resident CPU lifecycle fixture

2026-09-14. **Pass for source preparation; no blocker found in the reviewed
scope. Native execution remains unperformed and barred by the active FAULT
latch.** This review read source and computed three file hashes only. It did
not import Torch/Comfy, run fixtures, query devices/endpoints, change processes,
change settings, or mutate Git state.

Reviewed identities:

- Driver `test-host-embedding-resident-lifecycle-cpu.py`:
  `2a19169ac8b8a898294603f9216fdca96d3fd3efd5bcb1564d332de522b0b844`.
- Fixture `test-host-embedding-resident-lifecycle-cpu-fixture.py`:
  `4e2d0d92eea345dcb0ae36a4143f7f0d8887dda5c996845c37c6eba30673ee73`.
- Resident `host_embedding_resident_node_v2.py`:
  `bdaa14a06bd9937946eee470e562f6109df239273e905197d6e94fad28dd02f7`.

The driver retains the qualified integration driver's import order, sticky
accelerator traps, CPU availability policy, narrowly scoped import refusal,
unconditional compilation/backend traps, startup-before-Torch record and
first-failure stop. The real fault check remains the first source-gate action,
with no bypass argument; it also runs during integrity checks. Added pins bind
the resident, memory helper, fixture and prior actual-CLIP qualification.
Logical `torch.device('xpu:N')` construction does not enumerate a device; the
injected encoder target physically allocates and executes on CPU.

The fixture uses the actual CLIP constructor/clone, ModelPatcher loader and
native LoadedModel registry. Source review of the pinned model manager confirms
weak patcher/model ownership and real model-finalizer cleanup. Registry loading,
cleanup, weakref collection and resident release assertions are not mocked;
bulk unload is trapped. Both encoder and host patchers must appear in the actual
registry before transitions. Old-object weakrefs must die independently of
receipts. Registry absence is checked by the unchanged resident before allocating
a replacement; this avoids treating legitimate Python ID reuse as a leak. The
construction-refusal case checks absence directly, with no replacement allocated.

Clone, encoder-model and output-tuple survivors each prevent replacement and
latch further transitions. Fixture teardown happens after these assertions;
it cannot make an earlier failed ownership check pass. Teardown retires the
remaining successful component, drops fixture owners and uses native cleanup,
without mutating the model-manager registry list.

The roundtrip compares actual output bytes plus dtype, shape and stride for
control/host-table/control. This is a tiny CPU scaled-embedding/linear oracle,
building on the separately qualified original-CLIP integration; it does not
claim complete video/audio equality. Nonencoder factories/owners, checkpoint
geometry and available-memory observations remain explicit fakes. Their stable
identity and refusal-order checks do not establish full-model host memory
peaks, physical XPU placement/release, real-clip parity or speed. Those remain
separate future gates after the active hold is legitimately resolved.
