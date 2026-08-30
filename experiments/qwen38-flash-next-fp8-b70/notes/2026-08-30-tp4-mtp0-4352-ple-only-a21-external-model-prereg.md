# Qwen3.8 Flash-Next FP8 A21 external-model trace preregistration

Date: 2026-08-30
Status: frozen before GPU launch

A21 is A20 on isolated attempt 21/port 19693 paths with the supervisor's
owned-server assertion explicitly bound to the validated external checkpoint.
Generated launcher, client, and supervisor sources each agree on
`/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`. All A20 model revision,
runtime, PLE, MTP0, eager, cache, seed, request, authority, quality-helper, and
trace fields remain exact. Load time receives no credit; A16/A21's 149 tensor
digests remain the sole diagnostic comparison. No protected result changes.

Frozen artifacts:

- launcher wrapper `e60da9b46f31f43224d0564d519b801ee99ee133c042cacb4af1442da9bc18c5`,
  generated source `23629db3402b89b90cfe7a5ae302869c20ad576c913d4ba56c5b1654855973bf`;
- client wrapper `6f90e0b35496e61f808ed67b068ee84809bca39ab3644c333dfc5a46cf1a933a`,
  generated source `3362301864d8f031c90323d8266197ef7d89edf596778a5529dfa311d5cc17d5`;
- supervisor wrapper `38426910becab553eac6149e5a412f6b568af417ceb75d327e03c9e841133773`,
  generated source `51d2cefb2fbfb6bcb4be2228832c72b181492ceefe56e90beedde09d4145e4c7`.
