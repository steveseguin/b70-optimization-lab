# Qwen3.8 Flash-Next TP4 MTP3 official-quality result

Date: 2026-08-27

Status: **inconclusive and unqualified due to repeated-session stability; no answer-quality failure observed**

## Outcome

Attempt 2 passed the verified-local-model gate, four-rank collective, staged
runtime, host-placement, cache-capacity, healthy-API, and deterministic Door A
gates. Door A matched all 26 sealed MTP0 comparisons, repeated one hash 16/16,
returned the exact 4,096-token needle, and kept all 24 usage observations
complete and cache-zero. Its only semantic miss remained the inherited
deterministic target answer `30` instead of `14`.

Door B completed the four-case scout and 15 of 21 grid rows. All 19 returned
rows passed semantic, reasoning/final separation, normal-stop, usage, and
cache-zero gates. All 19 normalized and raw-hashed final answers exactly
matched the corresponding MTP0 official-quality answers. Only one reasoning
hash matched, which is expected to vary under the frozen sampled profile and
does not support exact-thinking parity.

The twentieth Door B request, `copy_phrase` at seed `2026082713`, stopped
advancing at 98 computed tokens and 33 output tokens. The scheduler still had
four tokens scheduled and recorded the speculative vector `[-1, -1, -1]`. The
fixed 300-second worker-response deadline then expired in `sample_tokens`; the
API returned HTTP 500 and the helper closed `request-error`. Six required grid
rows were never run. MTP3 official quality is therefore unqualified and
inconclusive. This is a repeated-session runtime boundary, not an observed
wrong answer, and this closeout makes no causal claim.

## Preservation boundary

This arm collected no timing. It does not replace or lower the existing exact
4K MTP3 result: `15.501565106 tok/s` decode median, `187.899186 s` median TTFT,
and `1.246260 tok/s` median wall output. The prior configured-512 and exact-4K
MTP3 capability receipts remain valid within their stated research scope.

Across this service session, Door A completed 24 model requests and Door B
completed 19; the stop occurred on model request 44. That history resembles
the existing repeated-serving boundary, but similarity is not attribution.
Any follow-up requires a new bounded preregistration; raising only the timeout
is not an authorized retry.

## Cleanup and host evidence

The application and engine manager shut down after the API error, but four
worker processes remained after the normal grace period. A forced
process-group stop was required. The kernel then recorded CCS and BCS engine
reset messages for each of the four B70s, eight messages total. Those messages
occurred at forced cleanup, after the request stop. Final receipts show no
relevant process, no listener on port 19647, four discoverable cards, and about
42.9 MiB used on each card.

The incident snapshot taken before forced cleanup contained no kernel entries
and no GPU event coincided with the request stop. The complete launch window
was not journal-clean: it contains corrected physical-layer receiver events
from the Samsung NVMe at `0000:01:00.0`. It contains no NVMe I/O error or
controller reset. The matching SMART receipt reports `critical_warning=0`,
`media_errors=0`, `num_err_log_entries=0`, and 4% used. These facts neither
prove nor suggest a storage cause.

## Evidence

Run root:

```text
/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-4352-r1-attempt2
```

The final 52-file manifest is `final-evidence-sha256.txt`, SHA-256
`5bbeb441c83f35a7a4eb8ea040e862fc1e2de375216b861eeec876648a491c17`.
Key receipts are:

- `quality-v2-control.json`:
  `323c1d8eaf1c615daf1ed872c792404156a1b8f7023c94720aaa2c75c2d8cfd9`;
- `official-thinking-quality.json`:
  `79cd22355ace5f76ab738f895bf4e5212c9d503121c7d54db94e5f5ec3d32f63`;
- `official-thinking-target-partial-comparison.json`:
  `4796ba6847f4dfa69b5051210c5edc27276858bb10d35b7a5745528233f6cc7f`;
- `server.log`:
  `764c14f712f06b3b2d9a87082235a26787aeb5021426a22ae4e06225adb1594d`;
- `20260827T2019EDT-official-case20-kernel-journal.log`:
  `19c4e28b2f54ea8f217db4e622b0a5c758efa7b77ce2dc0394b6d159568c0b2e`;
- `20260827T2023EDT-post-term-survivors.txt`:
  `07fd09993ff59ad756d71dd9052846b5fa50c72c2465eebdd994510d37d648ac`;
- `20260827T2024EDT-kernel-journal-final.log`:
  `ebf2ec60ea63733846854017458f38c8e3de2a0251ec641856bdf5ef7a0553d1`;
- `20260827T2025EDT-nvme0-smart-log.json`:
  `da8a8fcd7e8ba5f1f39f81d285a0e4079e9aa9719c26e1e5d7354d305e63ae56`;
- `20260827T2025EDT-nvme0-pcie-events.log`:
  `026f729070b3ecbc3bb01dd475c9f7fe90883a4f4c96b6bf71e94f548980222c`.

The structured closeout is
[`20260827-tp4-mtp3-official-quality-attempt2-result.json`](../data/20260827-tp4-mtp3-official-quality-attempt2-result.json).
