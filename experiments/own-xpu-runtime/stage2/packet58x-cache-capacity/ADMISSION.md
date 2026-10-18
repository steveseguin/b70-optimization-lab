# Packet58x admission — CPU analysis, October 18

The gate passes. The largest 256-byte-aligned cache under the retained
allocation allowances is **21,552,729,600 bytes**, an increase of
**3,552,729,600 bytes** over the 18 GB control. See [admission.json](admission.json)
for exact categories, nine completed window receipts and input hashes.

The calculation keeps the 32 GB physical floor, 1.5 GB reserve, both 1 GiB
workspace/transaction bounds, 256 MiB transfer allowance, 4K BF16 KV, recurrent
state, fixed weights and double pointer tables. It adds packet58v's
1,179,648-byte publication buffer and a separate **512 MiB driver allowance**,
larger than every observed DRM-minus-census difference plus 128 MiB. No
workspace is declared reclaimable. Fills write into the existing arena;
they do not require another expert arena. Physical allowance including the
driver is at most 30.5 GB. Actual expected allocation is lower because the
original conservative transient bounds remain intact.

The latest completed 58p/58r/58t/58v windows are checked for complete cache,
KV, native peak and supervisor samples. Packet58u's measured peak is never
lowered. Resident lookups in 58t replace their file allowance rather than
being counted twice. The new host requirement is **98,989,727,744 bytes**:
the measured floor, unchanged 4 GiB margin and 8 GiB reserve, packet58v's
metadata/staging allowance, and full host backing for every extra cache byte.
The live 4 GiB shadow stop stays in force. A new device run must independently
pass current host admission and its lifetime memory checks; historical room
does not grant a reservation.

The replay calls packet58j's unchanged global-LRU implementation on packet55's
independent held-out target routes, after checking the original converter and
native bindings. Compact route inputs retain the original order and hashes.
It starts empty and persists immutable weights across the twelve prompts.
All rejected speculative visits remain charged. The trace comes from two
ranks and admits after each layer, so it is a proxy for the one-card serial
schedule, not a native hit measurement or an async hit prediction.

| Cache GB | Replay expert hits | Replay miss MB / 48-layer equivalent |
| --- | ---: | ---: |
| 18 | 93.6765% | 60.160 |
| 19 | 94.4179% | 53.109 |
| 20 | 94.9497% | 48.053 |
| 21 | 95.4271% | 43.509 |
| 21.552730 | 95.6612% | 41.283 |

JSON retains miss bytes per route visit and per 48-layer position equivalent.
That equivalent must not be relabeled an emitted-token count. Applying the
miss-byte ratio to packet58p's measured fill payload and the existing 25 GB/s
copy-service proxy projects **+2.2614%**. It credits no zero-copy improvement
and no reduction in fixed publication or policy cost. The projection is
conditional on transferring independent demand and copy service to this lane;
it is not measured speed. Both registered admission thresholds pass (at least
2 GB extra and at least +2% projected). Device quality and speed are pending.

Reproduce with `nice -n 19 taskset -c 8-15,24-31 python3 -B admission.py
</dev/null` from this directory. The CLI alone installs its 4 GiB address-space
cap; imports do not alter runtime limits. No model payload, GPU, service,
queue, host setting or frozen packet was changed.

The completed packet58v bracket arrived during preparation. Its additional
57,344 bytes in the accounted peak are included in the final host requirement;
capacity and replay decision are unchanged. Its exact overlap outputs do not
clear the registered control-drift gate (14.73% versus 3%), so serial remains
the default. See maintenance-decision.json for the rechecked rates and pins.
