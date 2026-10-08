# Native continuation111 runtime

This is the fixed native reference for three connected49-frame chunks at640×384,
replayed once. The eight-request plan is banked separately in
`../20261007-continuation111-plan/candidate-plan.json`. Six complete F32 captures
retain all video/audio tensors. The first chain has145 unique video frames;
the second chain is replay evidence, not extra content. No quality adoption,
natural-seam, continuous-audio or speed-improvement claim follows from this code.

`session.py` admits the eight graphs in global order and requires an independently
reconstructed, durably accepted proof after each request. The first native and
first conditioned results therefore gate later generation. `integration.py`
registers the native preparation, predecessor provider and two-stage conditioning
nodes. It retains one owned, unchanged CPU F32 frame through both native calls
and the full native post-memory checks. `native_bindings.py` verifies actual
registered native code, resident VAE ownership, encoder cache cleanup, dtypes,
devices and unchanged NodeOutput handling. It performs no alternate arithmetic.

`proof.py` independently reconstructs each immutable prefix from request events,
source identity, controller observations, all four finite tensor payloads,
same-pass predecessor bindings and complete repeat hashes. Request evidence is
under the common root's `requests/`; captures are under `output/validation/`.
Only server observations, proofs and acceptances are under the server run.
`request_client.py` and `campaign.py` allow one submission per planned request,
bounded waits and one named proof action. Failure halts admission. Neither
controls application lifecycle; the successful application is retained.

Proof actions own the executor authority lock. Cancelling an HTTP waiter cannot
release admission while its thread is still running: owned cleanup waits for the
thread, latches failure, and only then releases the busy flag. Status requests
return409 while that action owns the lock instead of blocking the event loop.

The byte-identical `continuation_anchor.py`, `conditioning_guard.py`,
`encode_safety.py` and `capture_adapter.py` come from the separately reviewed
111 reference/safety packets. Their older inactive/future wording describes their
original standalone status; the new integration is their first runtime consumer.
Native safety, native adapter, setup validator, executor wrapper, observer,
serializer and all numerical model code are inherited from sealed110. The only
VAE source change adds the reviewed bound-controller encode-OOM refusal, retaining
the decoder refusal. No fallback retry, eviction, power, memory or cache-setting
change is added.

The exact110 successor builder replaces only explicit paths and retains changed
originals under `provenance/packet110/`. It verifies the external manifest before
importing successor helpers and reconstructs the full file inventory. Historical
110 optimized helpers remain source-bound but cannot be admitted by111's native
authority. Runtime sampler routes, lean installations and decoder replicas must
all be zero. Existing text-encoder qualification remains mandatory.

From the repository root, CPU-only checks are:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover -s experiments/ltx25-b70/recovery/20261007-continuation111-runtime -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python experiments/ltx25-b70/recovery/20261007-continuation111-runtime/runtime_packet.py --inspect-assembly
```

Default builder execution inventories inputs; `--inspect-assembly` additionally
checks the parent and constructs successor bytes in memory. Neither materializes
a packet or contacts the application. Explicit `--build` requires the reviewed
input-inventory hash and fresh50GiB reserve plus4GiB runtime plus384MiB build
admission. Reading/copying immutable110 source does not require stopping110.
The later controlled application reload, exact namespace check, sealed startup
verification and fresh health admission belong to the coordinator.

`reviewed-v1/` preserves earlier integration/session/binding/proof attempts and
their demonstrated defects. They are evidence, excluded from runtime assembly.
Current validation and operational status are recorded in the linked lane note
and repository `CURRENT.md`; source assembly alone never authorizes more than
the fixed eight-request plan.
