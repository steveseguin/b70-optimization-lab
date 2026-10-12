# Packet40 coordinator windows — prepared, not run

Run from the repository root, only after coordinator admission. `--card N`
is the first card of an adjacent pair (0, 1, or 2). W windows require a nice-0
parent. `taskset` may prefix each call; all ranks keep the inherited affinity.
The only supplied library environment is `LD_LIBRARY_PATH`, forwarded unchanged.
No device selector or tuning variables are permitted. The wrapper sets private
HOME paths for driver caches without claiming that file presence proves a hit.

```bash
set -e
p40=experiments/own-xpu-runtime/stage2/packet40-suite
p40_card=0
p40_receipts="$p40/receipts-firstcard${p40_card}-UNIQUE"
p40_oracle=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite/incident-retrospective
p40_suite64=experiments/own-xpu-runtime/stage2/suite-inputs-20261012/suite-manifest.json
p40_suite128=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
p40_k() {
  nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$p40/window.py" --authorized-device-window --card "$p40_card" "$@"
}
p40_k --window K0 --output "$p40_receipts/K0"
p40_k --window K1a --output "$p40_receipts/K1a" --k0 "$p40_receipts/K0/window.json" --dispatch "$p40/dispatch-p38.json"
p40_k --window K1b --output "$p40_receipts/K1b" --k0 "$p40_receipts/K0/window.json" --k1a "$p40_receipts/K1a/window.json" --dispatch "$p40/dispatch-p38.json"
p40_k --window K2 --output "$p40_receipts/K2" --k0 "$p40_receipts/K0/window.json" --k1a "$p40_receipts/K1a/window.json" --k1b "$p40_receipts/K1b/window.json" --dispatch "$p40/dispatch-p38.json"
p40_w() {
  nice -n 0 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$p40/window.py" --authorized-device-window --card "$p40_card" --controller native --input "$p40/build/input" --oracle "$p40_oracle" --dispatch "$p40_receipts/K2/run0/dispatch-measured.json" --k0 "$p40_receipts/K0/window.json" --k1a "$p40_receipts/K1a/window.json" --k1b "$p40_receipts/K1b/window.json" --k2 "$p40_receipts/K2/window.json" --w0p "$p40_receipts/W0p/window.json" --kd "$p40_receipts/KD/window.json" "$@"
}
p40_w --window W0p --output "$p40_receipts/W0p"
p40_k --window KD --output "$p40_receipts/KD" --input "$p40/build/input" --dispatch "$p40_receipts/K2/run0/dispatch-measured.json" --k0 "$p40_receipts/K0/window.json" --k1a "$p40_receipts/K1a/window.json" --k1b "$p40_receipts/K1b/window.json" --k2 "$p40_receipts/K2/window.json"
p40_w --window W2m-exact --max-new 64 --retain-steps 1-8 --output "$p40_receipts/W2m-exact"
p40_w --window W2m-speed --max-new 64 --retain-steps none --exactness-window "$p40_receipts/W2m-exact/window.json" --output "$p40_receipts/W2m-speed"
p40_w --window WS64x --suite-manifest "$p40_suite64" --max-new 64 --retain-steps 1-8 --output "$p40_receipts/WS64x"
p40_w --window WS64 --suite-manifest "$p40_suite64" --max-new 64 --retain-steps none --exactness-window "$p40_receipts/WS64x/window.json" --output "$p40_receipts/WS64"
p40_w --window WS128x --suite-manifest "$p40_suite128" --max-new 128 --retain-steps 1-8,97-104 --output "$p40_receipts/WS128x"
p40_w --window WS128 --suite-manifest "$p40_suite128" --max-new 128 --retain-steps none --exactness-window "$p40_receipts/WS128x/window.json" --output "$p40_receipts/WS128"
p40_w --window WSs --suite-manifest "$p40_suite64" --max-new 64 --retain-steps 1-8 --output "$p40_receipts/WSs-exact"
p40_w --window WSs --suite-manifest "$p40_suite64" --max-new 64 --retain-steps none --exactness-window "$p40_receipts/WSs-exact/window.json" --output "$p40_receipts/WSs"
p40_w --window W2mc --max-new 64 --retain-steps none --output "$p40_receipts/W2mc"
```

Exactness precedes speed so a speed receipt can hash its completed same-boot
companion. The companion must use the same binary/build, dispatch, card pair,
controller, cap and prompts. Exactness runs retain layer snapshots and are
speed diagnostics. Speed runs retain none and still compare every emitted
integer token with the sealed oracle, without tolerance. W2mc profiles classes
and is also diagnostic. WSs uses no draft; all other suite windows use MTP.

Each suite starts with a distinct synthetic warm-up and resets every mutable
allocation and host control before each measured request. Each selected prompt
runs once per attempt. `--repeat N` starts another separately reported attempt;
it never pools repeated prompts into cold evidence. A subset manifest is
accepted, explicitly labelled partial and cannot pass the final publication gate.
An exactness failure is recorded and the remaining requests still run; runtime
faults abort the window. No automatic restart or retry occurs.

The 128-token windows measure the 100-event/99-interval metric. They do not pass
the repository's final publication gate: its response cap is 512, and a separate
promotion attestation and fresh-device repeats are required. No submission is
prepared by these commands. No packet40 device speed has been measured.

Replace `UNIQUE` with a fresh attempt identifier. Coordinator receipts live
under this packet, outside ignored `build/`; they are durable window evidence.
Every destination remains inside packet40. Storage admission always reserves
the full write plus 8 GB on root and checks build remains below 3 GB; only
writes actually under build consume its projected-write budget. K2 reserves
2.5 GB for its full 66-length output and logs. After native receipt hash
verification, oversized `output.bin` files retain their digest, native receipt
and exact launch/dispatch restoration recipe, then are deleted without a
second compressed copy. Logs retain verified gzip bytes. Keep prerequisites
and exactness companions available through all their consumers.
K0's device image build has no CPU execution equivalent. CPU wrapper rehearsal
checks that branch's protocol and failures; it does not qualify a driver image.
