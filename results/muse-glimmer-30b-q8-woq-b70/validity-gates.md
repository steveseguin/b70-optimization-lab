# Validity and quality gates

## Passed

- two independent fresh-server canonical 256-token arithmetic means above 100;
- 15/15 frozen realistic prompts measured over 99 inter-token intervals;
- all 15 realistic requests reported `prompt_tokens_cached=0`;
- prompt-bootstrap one-sided 95% lower bound above 100;
- ARGMAX no-spec/spec token exactness for canonical code and JSON at 256;
- TOP_K reference token/content exactness for prose, code, and JSON at 256;
- exact code parity through 1024 tokens;
- JSON parsed as exactly 12 objects with requested keys/types;
- B-tree response covered node structure, ordering, fanout, logarithmic height,
  traversal, pages, and cache locality;
- 1024-token LRU answer compiled and passed get/put, recency, eviction,
  overwrite, capacities one and zero, docstring, and example gates;
- no drafter training.

## Deliberately not claimed

- BF16 or lossless equivalence;
- universal token exactness: ARGMAX prose diverged on a target-approved near tie;
- universal quality noninferiority versus the BF16 parent;
- every prompt above 100 tok/s;
- full-natural response throughput above 100;
- a deployed production endpoint.

The conventional 99-interval result is published at LocalMaxxing as
[`cmss8515c00n0ms01n3begqgg`](https://www.localmaxxing.com/en/runs/cmss8515c00n0ms01n3begqgg).

The raw classifications are retained under the standalone recipe's
`evidence/` directory and checked by `scripts/verify-evidence.py`.

The JSON/B-tree/LRU pass classifications were recorded in the chronological
closeout, but their one-off validator source/output was not preserved as a
standalone artifact. They are historical audited gates, not independently
rerunnable from this packet. A new publication or quality claim should rerun
equivalent validators and retain their source/output.
