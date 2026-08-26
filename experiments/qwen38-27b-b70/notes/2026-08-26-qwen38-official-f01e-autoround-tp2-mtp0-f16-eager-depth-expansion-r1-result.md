# Current-f01e AutoRound TP2/MTP0 eager F16 depth expansion R1 result

Result: **passed, Grade C, all six nonzero canonical depths**.

The current-image TP2 target-only profile passed exact 2K, 4K, 8K, 16K, 24K, and 32K requests in one server lifetime. Every request returned 128 token IDs, reported cache zero, passed the exact-depth gates, and matched the frozen current-f01e TP1 output at the same depth. Both TP2 workers, fresh ext4 cache isolation, direct model verification, the full quality battery, and cleanup passed. The TP4 quality comparison also matched completely.

Published decode uses `conventional_99_interval_tok_s`: 9.645823300859325, 10.041573627140547, 10.108015740743388, 10.12371796916948, 10.146000927730311, and 10.201853504519782 tok/s from 2K through 32K. These six points form a new current-f01e TP2 eager profile. They do not replace the older b2dd graph series, any TP2 historical result, or a protected route.

Context zero remains missing because the frozen exact-depth fixture has no empty active-context case. No graph, MTP/speculative, headline, protected, or LocalMaxxing authority transfers. Protected values 71.45427094575045, 30.329809361830037, 49.05894025767351, and 71.9001988117144 remain unchanged.
