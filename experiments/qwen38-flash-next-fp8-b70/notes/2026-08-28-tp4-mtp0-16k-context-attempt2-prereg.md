# Qwen3.8 Flash-Next FP8 TP4 MTP0 active-16K attempt 2 preregistration

Date: 2026-08-28

Status: preregistered after attempt 1 stopped before any request.

Attempt 1 proved the planned cache admission: the server became healthy with
21,795 reported tokens, all four exact 12.22-GiB placement receipts, and the
frozen 33-block allocation. The client then rejected the relative supervisor
script spelling before its first HTTP read or request. Controlled teardown was
clean; the one corrected host event addressed the local NVMe endpoint, not a
B70. This is preserved as a no-request control-flow receipt and has no matrix
credit.

Attempt 2 changes only fresh ownership/path identity:

- attempt 2 and port 19674;
- fresh run, cache, compile, RPC, supervisor-state, and evidence paths;
- the client resolves the live supervisor script through `/proc/<pid>/cwd` and
  its null-delimited argument vector before comparing the exact absolute path.

All model/runtime, TP4/EP4/eager/MTP0, placement, 16,512 context, 33-block
358,465,536-byte cache, one p16,384/o128 request, hashes, gates, time bounds,
Grade-D interpretation, and stop conditions remain exactly as preregistered in
`2026-08-28-tp4-mtp0-16k-context-prereg.md`. No second request is permitted.

Frozen attempt-2 packet hashes:

- long-context base: `d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1`;
- wrapper: `86708e16407c4b9a06d1e6e9f837c0001caf7f722bfe55814735b9e58e28f654`;
- supervisor: `b96c98ced5b38eed11110dbaf72a2f341f1001f9d903702ae3ab5cbd4b3195f9`;
- client: `12a5904dfe452766d50f9c3587344ec65cb40b9c80357a9ca44af2cf9b485fb9`.

Attempt 2 may start only after syntax/hash checks, exact-source checks, four
idle-card checks, port/path freshness checks, and an independent read-only audit.

## Observed result

Attempt 2 completed the one authorized request and controlled teardown.

- startup reproduced 33 blocks and 21,795 reported cache tokens;
- exact usage was 16,384 prompt, 128 completion, and 16,512 total tokens;
- cached tokens were zero, finish reason was `length`, and all 128 token IDs
  were returned;
- all 25 generic exact-depth checks passed;
- output-token SHA-256 is
  `5706b3445c50abaaedacae0e5f52739856300701374126c23d610367c1dd1d39`;
- text SHA-256 is
  `efadb89d58154caa3b4c0f6e7816f75b1d4e57eae3d24fbbdb8f03d4094048d3`;
- elapsed time was 1,097.9810 seconds, TTFT was 1,073.5426 seconds, and the
  conventional diagnostic rate was 5.219484116949911 tok/s;
- supervisor exit was zero, no listener/process/temp-path residue remained,
  and all cards returned below 43 MiB;
- the host journal contained 36 corrected Source-514 reports and 46 RxErr log
  lines, all addressed to local NVMe `0000:01:00.0`; there was no B70-addressed
  reset, fatal, or timeout event.

The 49-entry raw manifest verifies and has SHA-256
`d1cbe2533ca024bbadf725163a0ce22cb268a54b42d83ac65cc2dd08984d1363`.
The cell is classified Grade-D quarantined capability: semantic oracle,
repeat, and fresh-server-repeat gates remain absent. The rate is diagnostic
only and receives no speed, curve, quality, deployment, or headline credit.
