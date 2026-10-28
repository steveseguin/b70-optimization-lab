# Dedicated all-owner reset A/B/A64K — closeout

<!-- campaign-closeout -->

## Question and identity

Can the same three target owners and dedicated draft reset between independent realistic requests and reproduce the first request after a different one? Binary`e60f7427…`, reference target routing, unchanged BF16 draft, cuts0/17/33/48, context65,536, depth3, prefill256 and four transport slots; three512-output requests in A/B/A order.

## Outcome

**Passed the bounded all-owner reset/repeat gate.** All four owners exited0, no live PIDs remained, and passive postflight matched the known fault baseline with no holders. Requests01/02 each matched startup cold state across **4,091,763,958 physical bytes**; repeated A matched its first execution across the same byte count. Inventories include2,065 canonical target sources,27 inactive-bank sources and73 provider sources. Prepared launch-cache extents remained authenticated.

All1,536 actual output IDs match the saved generic962046 CPU-qualified continuations on identical prompt bytes. This covers **two unique prompts/1,024 unique saved output tokens**, not three new CPU runs or the full12-case suite. It does not establish bitwise CPU states, depth2 reset qualification,262K reset qualification or a performance record. [Summary](summary.json), [saved-output proof](saved-cpu-output-proof.json).

## What worked

The existing all-owner controller used native reset, exact physical cold comparisons and repeated-request output/state checks within one owner lifetime. No bank exclusion or fresh-server chain substituted for reset. Cold duplicate payloads were removed only after the controller's full-byte proof and alias receipts.

## What failed or remains uncertain

No failure occurred in this completed gate. The full12-case realistic performance suite and matched fixed depth2/3 qualification remain separate next work. Broader fidelity/default promotion remains unqualified.

## Evidence and patches

[Index](index.json) retains400 compressed metadata/log/source artifacts, including exact plan/source pins, launch commands, terminal, cold/repeated proofs and alias receipts. All56 plan pins were verified, including binary SHA256`e60f7427d5737bee1e4e521ffbad1c77f4ea687fbb86bd542f05fb495eb9e378`.

[Archive receipt](run/state-archive.json.gz) preserves15 exact state bundles under `/mnt/raid-models/ownrt-experiment-archives/2026-10-28/dedicated-reset-aba64k-r1/state-bundles.tar.zst`:425,740,277 compressed bytes, SHA256`1b4f2e85e2fbc065c123f8d8a1ba3895b19749f9779dabd77024c7434cb7b2ba`. Every archive member was compared byte-for-byte with its stable original and full seal before unlinking exactly12,794,116,776 raw bytes. Metadata and transport maps remain.

First-A, final-A and startup-cold members have explicit roles/member names/seals in the receipt and summary, preserving depth2 comparison references. For example, first-A target0 is `output/stage0/native/state-2147483646/state.bundle`; final-A target0 is `output/stage0/native/requests/request-02/state-2147483646/state.bundle`. Use `zstd -dc ARCHIVE | tar -xOf - MEMBER` to recover a selected member to an explicitly fresh output. Whole archives were not reread during this closeout beyond the new archive's required verification. [Run-specific helper](archive_helper.py).

## When to revisit

Reuse the archived first-A/final-A oracle for an exactly matched depth comparison. Run the existing full12 cold/reset suite under a separately registered identity, retaining its quality and fair timing gates; do not repeat this unchanged bounded reset gate without changed risk.
