# Qwen3.8 Flash-Next FP8 A17 fresh trace preregistration

Date: 2026-08-30
Status: frozen before GPU launch

A17 is the required fresh-start peer for A16. It changes only isolated run,
cache, temporary, supervisor, and port identities from attempt 16/port 19688 to
attempt 17/port 19689. vLLM head, kernel head, staged runtime, model revision,
PLE-only placement, cache capacity, graph/MTP/scheduler flags, seed, request
order, client battery, trace threshold, and trace implementation are exact.

Interpretation is frozen:

- compare A16 and A17 trace labels and tensor names in order;
- if model inputs differ, stop at the embedding/input boundary;
- otherwise report the first layer tuple tensor whose SHA-256 differs;
- if all 149 tensor digests match, classify the synchronous trace as
  stabilizing or insufficiently sensitive and do not invent a layer cause;
- ordinary timing receives no credit, and any client assertion remains
  fail-closed.

Frozen artifacts:

- launcher wrapper `083b0af6b0632ab547cc86553bec19104386fae1cb73da791baf9957ecfeddc0`,
  generated source `6fbeb749563f4459c9efb105f1c8d3b60a4f2eb7b6ad79dec98aedbca04e5b0c`;
- client wrapper `3d52f02efe0794a76ed1eb12311299126612b86dc3cbd3062df1d8fcdd0ba7c9`,
  generated source `d3f2b7d7c320a856b4221ec7d76c5aa71959bb74080d94609e607ea0b300ec15`;
- supervisor wrapper `16bd4f513f50c3fdc429246af95d4df7e1efad683b864ae26c73c691e800e98d`,
  generated source `10311a780e27b5edc35ba5760fa2b2b30cc388603c47c16b28831ba9e0f430f0`.

No protected result changes in A17.
