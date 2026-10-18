# Packet58p boundaries

- Never run this chain on a partial screen, fewer than twelve exact prompts,
  or less than 0.5% over either control. Read native receipts again; `ready.json`
  is a report, not an authorization token.
- Never reseal a started chain or repair its submission tool afterward. Finish
  tools, CPU checks and pins first. `seal.py` refuses existing chain output.
- Never pin mutable parent orchestration, readiness or queue outputs. Copy
  immutable inputs and keep the live record threshold outside the build seal.
- Never let lane B overlap any of the seven windows. Whole-host scope does not
  convert WS128x into a second timing run. Preserve all 58g memory bounds.
- Full-size startup alone does not exercise launcher parsing. Use both the real
  native parser and initialize/prepare_plan/prepare_commands, plus the actual
  host-oracle consumer for every model window and both miss paths.
- Use the validated saved kernel capture's newest timestamp minus two seconds;
  never the exact newest timestamp or current wall time.
- Preserve the 128-token scope, false strict 512-token gate and missing second
  timing repeat. A CPU pass is neither tile16-only device parity nor a speed result.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
