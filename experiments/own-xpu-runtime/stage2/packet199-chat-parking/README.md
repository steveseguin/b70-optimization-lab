# Packet199: real-text HTTP chat and bounded parking

This packet prepares one warm card0 owner with the **unchanged packet198 device
binary** (`c9b401089d95eeb152953a8c0d82d0678de2474934941bc6c97abd4b03287875`).
CPU readiness is sealed: 9 worker, 2 seal-failure and 17 controller checks pass,
with 215 source files and 35 interpreter/dependency files pinned. No native model
execution or service change occurred during preparation. [plan.json](plan.json)
fixes the reviewed pilot; [vectors.json](vectors.json) fixes real messages, exact prompt
IDs, recorded reference outputs and expected parking decisions.

## Six sequential HTTP turns

All requests use non-streaming greedy `/v1/chat/completions` on one literal
`127.0.0.1` ephemeral listener. The coordinator supplies private session headers;
clients cannot choose engine identity, checkpoint paths or parking budgets.

| Row | Session/policy | Prompt IDs | Cap | Preregistered gate |
| --- | --- | ---: | ---: | --- |
| A park | `p199-a`, 512 MiB main policy | 87 | 256 | Exact p198 `fresh-a` input and output; SAVE. |
| B park | `p199-b`, main policy | 60 | 128 | Exact p198 `fresh-b` input and output; SAVE. |
| A chat append | `p199-a`, main policy | 370 | 128 | Exact 343-token saved prefix plus 27 newly rendered tokens; restore then SAVE. |
| Fresh chat reference | `p199-fresh`, main policy | 370 | 128 | Same real messages and input IDs, fresh prefill; exact generated tokens and checkpoint state versus the append row. |
| Edited A | `p199-a`, main policy | 394 | 128 | Initial user text changes token 3, before any unknown appended reply; prefill then SAVE. No prerecorded output oracle is claimed. |
| Final B without parking | `p199-final-b`, separately admitted zero-budget policy | 60 | 128 | Exact p198 B output; normal no-save RELEASE, then clean stopped. |

The total generation cap is 896 tokens; new chat/edited prompts may stop earlier
at native stop IDs **248044 or 248046**. Native geometry is unchanged: context4096,
vocab248320, full BF16 KV/state, one card, no quantization/precision change. Both
finish reason and presented text must agree with the actual raw generated IDs.
The first A/B reference streams contain neither stop ID and require `length`.

The actual pinned renderer/codec was used to prepare these vectors. A's 256
recorded output tokens decode and encode exactly, with no trimmed tail; its
343-token visible history is an exact prefix of the 370-token continuation.
The added user text is “Continue with the next concrete steps and identify who
owns each action.” Native append processes the prior pending token plus the
27-token delta. The edited initial user message guarantees a prefix miss
regardless of the append row's not-yet-known completion.

P198's old 469-token append input was a raw document-token extension, not this
rendered chat conversation. Its output is **not** an oracle for the new 370-token
prompt. The new append gets its exact reference from the fresh row in the same
owner. A 384-token p198 reference also exists for the original A prompt but is
recorded as unused, avoiding an unnecessary seventh request.

## Bounded parking and storage

The global main policy remains **512 MiB**, with the explicitly injected
**256 MiB SAVE bound** proven for this exact p198 context4096 writer/geometry in
the [size-bound receipt](../../integration/receipts/p198-checkpoint-size-bound.json).
Each charge conservatively includes metadata/tokens/staging. Row 3 evicts B
before writing the new A checkpoint, preserving old A until its replacement is
visible. At most two reservations coexist. The final zero-budget policy shares
the same owner and adds no parked bytes; the coordinator switches ChatService
only between requests after confirming no active handler, and records that
selection. This is an admitted fixture choice, not an HTTP option.

The selected checkpoint root is fresh private local ext4:
`evidence/runcheckpoints`, created exclusively with actual owner UID and mode
0700. Root must retain **27,000,000,000 bytes after a 640 MiB forecast**: 512 MiB
checkpoint peak plus 128 MiB for worker/cache/logs and one endpoint restoration.
Admission must recheck free bytes after root's separately verified closed-p184
archive/prune. No floor is lowered and no unverified artifact deletion is part
of this packet.

An external USB root was considered because earlier local margin was too small.
Read-only mount inspection found fuseblk `/dev/sda2`, root UID0/mode0777; actual
owner-private0700 could not be established without a probe. Root selected local
ext4 after verified archival instead. [fs_smoke.py](fs_smoke.py) is **unused
planning evidence**, not a required gate or a command to run. No external
directory, test file, mount setting or power/memory setting was changed.

## Completion and admission boundaries

The worker must retain exact HTTP payloads/responses, native request IDs,
input/output tokens, policy decisions, typed delete results, every SAVE/RELEASE
event, checkpoint manifest/control evidence and compared state hashes. It must
match the A/B references before sending their dependent requests. The fresh row
must equal append raw tokens and full native state. An edited-prefix miss is a
policy outcome, not a token-exactness qualification for that unreferenced prompt.

Final RELEASE must precede stopped with six completed requests and controls,
no discarded pending reply, successful native exit and passive device drain.
Only then may the established one-shot controller restore the three owner's
daily applications once. Preserve both queues, PAUSE-B, external STOP bytes and
the existing exact fault review. No request follows a new fault; any incident
action is a single cooperative owner drain, never restart/retry/reset/reboot.

Root owns worker/controller review, source freeze, read-only live admission and
launch. Seal only after final HTTP, codec, bridge, store, policy and worker source
identities and production argv are reviewed. CPU readiness precedes separate live admission by the coordinator. There is no latency, cold-speed or throughput claim from this functional
pilot. The original CPU vector preparation command is retained below. Do not regenerate
sealed vectors in place; preserve any future revision separately:

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet199-chat-parking/prepare_vectors.py
```
