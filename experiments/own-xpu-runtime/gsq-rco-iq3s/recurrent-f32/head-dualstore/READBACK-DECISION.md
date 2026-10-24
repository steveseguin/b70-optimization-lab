# Deferred after shared-prefix readback

The [closed unchanged-engine replay](../operating/prefix-replay-a/RESULT.md)
measured native logits21.0 for token220 and20.625 for264. They are distinct,
so final BF16 rounding cannot reverse their strict order. This rules out the
proposed head observation as an explanation for this pair; no build or wiring
was performed. The partial source, its failed preliminary path-root test, and
its limitations remain preserved. The owner requested wrap-up. Any future work
should address the earlier precision contract rather than completing this
side channel by default.
