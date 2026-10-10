# H3 published input correction — 2026-10-10

The denoiser was published by Comfy-Org, not produced by this lab. The lane's
`minimax-h3-download-pruned.sh` downloaded it into turin's existing Comfy model
root; its read-only copy is [preserved here](download-pruned-script.txt). The
September 17 AdaLN note is an analysis of that file. The fit directory and
recovery plan are superseded history. Both erroneous recovery intake catalogs
now have zero entries: no lab input needs downloading.

The owner accepted this exact model on October 10 ("appropriated denoiser ...
package it"). That approval includes the Comfy-Org source exception; it is
recorded in AGENTS.md and [owner-decision.json](owner-decision.json). The measured
run and recipe target **turin (`steve-TURIND8-2L2T`), two B70 cards and 15 GiB RAM**.
The four-card host was only used for this CPU documentation correction.

## Identity receipts

[Publisher metadata](publisher-metadata-verification.json) was fetched from the
immutable HF revision APIs without downloading weights. [Local file receipts](turin-file-verification.jsonl)
record sequential read-only hashing on turin via SSH at nice 19 with
`OMP_NUM_THREADS=2`. Each record includes size, SHA-256, Git-blob SHA-1,
completion time, and unchanged size/mtime across the read. Files were read in
8 MiB chunks; no model library, GPU, service or device was used. Small files
match publisher Git-blob IDs, and all weight hashes match publisher LFS SHA-256.
The [manifest](model-manifest.json) now records those local verifications.

The denoiser is 40,225,724,176 bytes, SHA-256
`a32572fb90b5508b201ec7c2eddcc184b13ddfd3c6f6d2cf06a0b46535d541b4`;
the INT8 encoder is `bc2ced0fbea64757fa9acddccfc0b3f4819d1dcf1da6c124d690d368be283923`.
This independently checks the file identity the reviewer reported at 22:45 UTC.
Verification now binds the existing lane inputs; it does not retroactively
create a hash log at the time of the historical execution.

## Publication reassessment

The [Comfy-Org source card](https://huggingface.co/Comfy-Org/MiniMax-H3/blob/e5eb578a89295337b8ff433a035929ce0279e0b6/README.md)
identifies the repackaged files and points to the
[MiniMax-H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE).
Source attribution, owner approval and the documented license position pass;
this packet distributes no model tensors. This is not an unrestricted license
claim. The guide preserves the applicable territory and other conditions.

Weight identity is now pinned and locally verified. Fit reconstruction is not
a required reproduction step: obtain the published files at their pinned URLs.
The 800.8 s/clip baseline still lacks raw receipts, and September reference
receipts remain absent. The 396.625 s/clip eight-clip batch remains receipted;
32 matches and eight clip repeat passes are session evidence, not an independent
fresh full-suite repeat.

Under [the publication standard](../../docs/recipe-publication-standard.md),
source/runtime closure, a clean build and smoke test, independent full-suite
quality/determinism evidence, portable path/stop qualification, public native
release assets and clean-host replay remain open. The native-video-draft
contract requires all three build/smoke/quality certification flags to stay
false and forbids `published`; no new evidence clears them here. Status remains
**draft**, package **candidate / expert**, strict metric **null**. The website
can publish this corrected scoped result without claiming a certified rebuild.
[Machine-readable gates](publication-gates.json).
