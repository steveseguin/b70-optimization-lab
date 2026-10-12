# Coordinator windows: prepared, never executed by this agent

Use the final sealed build-receipt.json. A missing CPU gate is a refusal, not
permission to bypass it. Run the chain inside the coordinator's systemd user
unit so an agent-shell exit cannot interrupt a GPU job. The unit must allow the
wrapper to stop its ranks cooperatively. All W windows start from a nice-0 parent; taskset may
wrap that parent and affinity is preserved. K windows use nice19 and idle I/O.
Only supply your existing LD_LIBRARY_PATH; it is forwarded unchanged. Do not
set device selector, cache or precision variables. --card names the first card
of the adjacent pair. Each capacity needs its own full chain and fresh output
paths. A window never retries a failed child.

From the repository root, set the admitted pair and capacity. Execute this
sequence once with context 4096, then once with context 32768. The suite defaults
to the 128-token manifest; the 64-token path below is also accepted.

```bash
set -euo pipefail
packet44=experiments/own-xpu-runtime/stage2/packet44-context
packet44_card=0
packet44_context=4096 # second independent chain: 32768
packet44_out="$packet44/build/c$packet44_context"
packet44_input="$packet44/build/input"
packet44_oracle=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
packet44_suite=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
# Alternative: experiments/own-xpu-runtime/stage2/suite-inputs-20261012/suite-manifest.json
packet44_k=(nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet44/window.py" --authorized-device-window --card "$packet44_card" --context "$packet44_context")
packet44_w=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet44/window.py" --authorized-device-window --card "$packet44_card" --context "$packet44_context")
"${packet44_k[@]}" --window K0 --output "$packet44_out/K0"
"${packet44_k[@]}" --window K1a --output "$packet44_out/K1a" --k0 "$packet44_out/K0/window.json" --dispatch "$packet44/dispatch-p38.json"
"${packet44_k[@]}" --window K1b --output "$packet44_out/K1b" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --dispatch "$packet44/dispatch-p38.json"
"${packet44_k[@]}" --window K2 --output "$packet44_out/K2" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --dispatch "$packet44/dispatch-p38.json" --seconds 10800
"${packet44_w[@]}" --window W0p --output "$packet44_out/W0p" --k0 "$packet44_out/K0/window.json"
"${packet44_k[@]}" --window KD --output "$packet44_out/KD" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --input "$packet44_input"
"${packet44_w[@]}" --window W2m --output "$packet44_out/W2m" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --w0p "$packet44_out/W0p/window.json" --kd "$packet44_out/KD/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --input "$packet44_input" --oracle "$packet44_oracle" --controller native
"${packet44_w[@]}" --window WS --output "$packet44_out/WS" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --w0p "$packet44_out/W0p/window.json" --kd "$packet44_out/KD/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet44_suite" --controller native --repeat 2
"${packet44_w[@]}" --window WSs --output "$packet44_out/WSs" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --w0p "$packet44_out/W0p/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet44_suite" --controller native --repeat 2
```

The suite reads its token cap from the manifest and checks every emitted token
against that oracle. It checks the binary's retained steps 1–8 against the
corresponding oracle files; it does not invent steps97–104. Reports carry both
63 intervals (tokens 1–64) and, when present, 99 intervals (tokens 1–100), with
counts, numerator and timestamps. A 128-token cap is not the 512-token promotion
gate. No public speed claim follows from CPU preparation.

Memory admission uses memory-plan.json separately for each rank/capacity and
compares the actual owner census before HALF. The floor is 1.5 GB per card.
K2 reservations are 297/1840 s for 4096/32768; the 10800 s watchdog passes the strict
quarter rule. Unknown actual long-context duration remains a coordinator check.
Do not infer context support from a short prompt's exactness alone: K1 covers
long synthetic positions and W windows establish physical execution/residency.

Storage failures never become device-fault latches. Post-run compression errors
keep raw evidence and the completed verdict. For a fresh fault signature or an
owner that failed after device contact, preserve evidence and follow coordinator
recovery; do not retry automatically.
