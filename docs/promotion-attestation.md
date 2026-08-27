# Promotion attestation

Passing `scripts/bench-openai-realistic-suite.py` proves only that the speed
workload met the fixed representative-suite and no-cache rules. Before a result
can become a package headline or external submission, create a separate JSON
attestation that binds that exact performance file to independent quality and
determinism evidence.

The submission builders require `--promotion-attestation /path/to/file.json`
and validate this schema with `scripts/promotion_evidence.py`:

The primary speed is the median of the per-class medians, so prose, code,
analysis, operations, documentation, and structured-writing inputs receive
equal headline weight even though the fixed suite contains different numbers
of prompts in each class.

```json
{
  "schema": "neural.download.promotion-attestation.v1",
  "performance_evidence": {
    "path": "relative/path/to/realistic-suite.json",
    "sha256": "sha256-of-that-exact-file"
  },
  "identity": {
    "model_revision": "immutable-model-revision",
    "runtime_revision": "immutable-runtime-or-image-revision",
    "optimization_identity": "digest-or-exact-name-for-patches-env-and-flags"
  },
  "gates": {
    "varied_task_quality_passed": true,
    "exact_or_target_oracle_passed": true,
    "deterministic_repeats_passed": true,
    "fresh_server_repeat_passed": true,
    "target_model_unchanged": true,
    "no_quality_loss": true
  },
  "quality_evidence": [
    {
      "path": "relative/path/to/quality-result.json",
      "sha256": "sha256-of-that-exact-file",
      "supports": [
        "varied_task_quality_passed",
        "exact_or_target_oracle_passed",
        "deterministic_repeats_passed",
        "fresh_server_repeat_passed",
        "target_model_unchanged",
        "no_quality_loss"
      ]
    }
  ]
}
```

Relative evidence paths should be repository-relative. Every referenced file
must exist and match its SHA-256. The attestation is a review decision, not a
replacement for evidence: it must state the exact model, runtime, patch/env
identity, oracle, repeat policy, and quality scope in the referenced files.
Every required gate must appear in at least one artifact's `supports` list;
unbound booleans fail closed. Submission builders also require the attested
runtime revision to match the exact runtime identity being submitted.

Do not set a gate to `true` because a nearby model, another quantization, a
different card topology, or the unoptimized path passed. If the optimized path
does not have a registered oracle or fresh-server repeat, the honest result is
`featured_metric: null` and **strict headline pending**.
