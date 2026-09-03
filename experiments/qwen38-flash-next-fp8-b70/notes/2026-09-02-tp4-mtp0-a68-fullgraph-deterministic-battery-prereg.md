# Qwen3.8 Flash-Next FP8 A68 full-decode-graph deterministic battery preregistration

Date: 2026-09-02
Status: frozen before launch; first battery on a logit-exact TP4 server;
promotion possible only if every frozen gate passes

## Question

A66 (eager) is logit-exact at depths 8-2048 and A67 (full decode graph,
public oneCCL twoshots, tuned M1 W13-N32 map) is logit-exact at every point
it reached before the supervisor's bounded-read guard stopped it, both with
`VLLM_XPU_MKLDNN_DETERMINISTIC=1`. Does the A67 server pass the frozen
client battery that A56 passed (recovery canary, 7 exact semantic cases with
the known `code_execution=30` miss allowed, 16/16 repeat on the protected
hash, exact cache-zero 2K needle, three short rows, two exact-2K rows), and
what does it measure?

## Design

`tools/rewrite-q38-a67-to-a68-battery.py` derives A68 from frozen A67 with
fresh attempt paths (attempt 68 / port 19740) and one guard change: the
bounded root-NVMe read cap in the launcher pre-check and in the supervisor's
per-second and postflight guards rises from 16,777,216 to 134,217,728
sectors. A66 and A67 showed 3.4 GiB per minute of root-NVMe reads while
serving (mapped runtime pages re-faulted under the server's host-memory
pressure) with NVMe and root-port AER counters at zero; the AER guard (at
most 64 corrected events per run) is unchanged. The server identity is A67's
byte for byte. The frozen A56-lineage client
(`run-tp4-mtp0-2304-ple-only-a68-fullgraphdet-w13n32-client.sh`) runs after
health instead of the probe. Packet hashes are printed by the generator and
pinned in the supervisor and host wrapper.

## Reading

- All client gates pass: the first deterministic, quality-passing TP4
  graph endpoint. Its short-row median is reported against A56's
  `23.626811 tok/s`; a fresh-server repeat (A69, same packet, fresh
  attempt) is required before any promotion, and the logprob probe on the
  same identity is already exact (A66/A67).
- The 16-repeat or a semantic case returns a different hash than the
  protected one: the deterministic rounding changed a token-level output.
  The outputs are then judged on the semantic cases and the needle, and the
  question of a new authority goes to the user; nothing is overwritten.
- Any hang or fault: recorded as before; the deterministic flag is not
  implicated unless the hang class changes.

Protected results remain unchanged by this arm.
