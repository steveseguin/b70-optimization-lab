# Exact publication change to build

Qualifying components: device_publication_and_drain.
For construction/upload/scatter: build only changed final pointer/generation entries and preserve exact full-table fallback. For device_publication_and_drain: investigate retaining dependency ordering and staging lifetime through subsequent same-queue work instead of a blocking poll at publication; never remove a reader fence or reuse staging early. Preserve revocation and fill completion. Measure replacement overhead; retain BF16 KV and resident lookups. Require byte parity, iq3-p49-split32-v1 oracle and two fresh-process repeats before any speed claim.
