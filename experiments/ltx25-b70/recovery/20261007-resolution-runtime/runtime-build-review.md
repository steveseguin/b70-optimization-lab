# Independent CPU review of packet101 builder and campaign

Reviewed October 7, 2026. **No remaining material blocker identified in the
reviewed builder/campaign versions.** This is source/lifecycle review, not a
runtime admission, GPU test, exact-output qualification or measured memory bound.
The coordinator owns production fixes, actual source materialization, runtime
identity sealing, launch and all device operations.

The reviewed source hashes are:

| File | SHA256 |
| --- | --- |
| `runtime_packet.py` | `2f1563dde66b3ac9912d4cc375d2892f033a1403c1d81c8eb8ff0d3eea9ce34f` |
| `campaign.py` | `91816bfec10ad4e2b468de5ea7294d2d8fc6f233f18f6e15682b142979b3ef21` |
| `integration.py` (phase/resource interface inspected) | `5afe762a692a842ba9be22ca567361028698713c0119780c3d7a5f6ee768a620` |
| `schedule.py` | `5b0e6c52aef229cd458129ee5a3c74c7535efe789fa550b1ac859c9853de34ca` |

## Findings fixed during review

1. The native OOM source overlay changes `comfy/sd.py`. Both inherited NA
   startup nodes still pinned its old hash and would refuse application startup.
   The builder now applies an explicit matching `SD_SHA` delta to
   `source/scripts/na_axis_decode_node.py` and
   `source/custom_nodes/ltx_na_axis_decode_lab/__init__.py`. The CPU control
   parses both real transformed literals and compares them with the new sd bytes.
2. The campaign previously entered graceful shutdown even if its own execution
   refused an existing campaign-start ledger. A duplicate invocation could stop
   another invocation's server. It now holds a campaign lock and sets ownership
   only after exclusive durable start; nonowners neither signal nor overwrite
   the final campaign result. A synthetic duplicate invocation verifies this.
3. Missing preview counts previously defaulted to idle. Both actual preview
   fields are now required. Tests cover missing counts and pending queue,
   pipeline and preview work.
4. A first SIGTERM arriving during normal closeout could interrupt the existing
   bounded stop. SIGTERM/SIGINT now latch during closeout instead of initiating
   another interruption. The test invokes the installed handler as a plain
   Python function during mocked stop; it sends no operating-system signal.

## Builder and provenance

The default path only reports a plan. Build requires the explicit stopped-parent
assertion and reviewed component inventory digest before destination creation.
The immutable parent is qualified99b, manifest
`f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
The successor has its own fixed path and run name; changed parent files are
retained as provenance. There are14 explicit component inputs. Verification
hash-checks all manifest entries before importing successor transform helpers,
then reconstructs the exact delta, extras and full inventory. Inherited runtime
and RoPE provenance remain intact; qualification remains false.

The source-only build admission requires50 GiB available after a384 MiB
allowance. Metadata inspection of the exact parent manifest's1,627 listed files
found107,730,643 logical bytes (102.740 MiB). The allowance comfortably covers
that source copy plus the small overlay/provenance additions; no model weights
are copied. CPU controls exercise low-space refusal before destination creation,
but do not execute a successful build or simulate a full filesystem copy.

The successor launcher retains GPU preflight before RoPE installation, one
final server identity, strict determinism restoration, integration installation
and then `main.py`. The source delta and tested launcher compile. The explicit
environment rejects inherited W2/256 or20/28 configuration; intended control
is W1/B1,23/25,640×384, shared pool and card2 decoder replica.

## Campaign and resource admission

The current schedule contains32 distinct submissions: seven setup requests
plus25 plan requests. There are26 requests with capture nodes, within the32 raw
capture allowance. It creates no server and performs no retry or restart.
The tests execute the complete schedule against an async stub, checking exact
request order and memory/quality barriers, then separately exercise terminal
failure without retry.

Graceful stop requires ownership, two observations of settled prompt/pipeline/
preview work, the same process identity and no recorded GPU fault. It sends one
SIGINT only, waits at most180 seconds after that signal, and never escalates.
Pre-signal quiescence itself has a separate bounded wait. All test endpoint,
signal and sleep operations are replaced with CPU stubs; fault, changed PID,
unresolved work, repeat stop and deadline exhaustion never result in an extra
signal. Final four-card health and driver observations remain coordinator work.

The integration's `admit-capture` checks fresh synchronized physical free
memory6/6/2/7 GiB; `admit-decode` checks2/2/7/7 GiB. It verifies retained
native object ownership against the prepared controller before each stage.
These remain **engineering allowances, not strict peak guarantees**. The native
640 VAE historical full peak was3.508 GiB, including about1.71 GiB of both VAE
weights. A7 GiB card2 threshold leaves roughly5.29 GiB after that weight copy,
consistent with the inherited replica helper's5 GiB post-copy gate; actual
replica construction/probe and freeze must still pass. The4 GiB allowance above
the sampler floor is not a measured full48-block capture bound. No claim here
allows bypassing fresh post-stage/freeze checks, OOM refusal or fault halt.

## Verification

Executed offline:

```
python experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_runtime_packet.py
python experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_campaign.py
```

**9 builder controls and9 campaign controls passed.** No packet was built,
source tree copied, endpoint contacted, real process signaled, model invoked
or GPU API called. Test fixtures used temporary local directories only.
Independent safety/adapter and reference/geometry reviews are separate evidence;
this review does not substitute for them or for the forthcoming runtime check.
