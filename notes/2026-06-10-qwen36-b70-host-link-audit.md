# Qwen3.6 35B Quark W8A8: B70 host/link audit

Date: 2026-06-10

## Why this audit happened

External B70/vLLM material repeatedly points to host stack, PCIe policy, power management, and driver/firmware state as large performance variables. Because the current Qwen3.6 W8A8 path is stuck around `99 tok/s` corrected after-first for a single request, I did a read-only host audit before continuing with smaller kernel changes.

## Repro artifact

- Script: `scripts/audit-b70-host-links.sh`
- Output: `data/qwen36-b70-host-link-audit-20260611.txt`
- Runtime-policy dry-run script: `scripts/tune-b70-runtime-performance-policy.sh`
- Runtime-policy dry-run output: `data/qwen36-b70-runtime-policy-dryrun-20260611.txt`
- Short load sample: p512/n256 direct-backend decode stayed healthy at `98.5261 tok/s` corrected after-first and `96.0837 tok/s` e2e, so the backend was not broken during this audit.

## Findings

- Host stack:
  - Ubuntu `24.04.4 LTS`
  - Kernel `6.17.0-29-generic`
  - Four Intel Arc Pro B70 cards: `0000:23:00.0`, `0000:27:00.0`, `0000:43:00.0`, `0000:47:00.0`
- PCIe ASPM policy is still `[default]`, not forced to `performance`.
- B70 endpoint runtime power control is `auto` on all four endpoints.
- The root/first Intel bridge hop reports expected x16 links:
  - AMD root ports: `16.0 GT/s x16`
  - Intel upstream bridges (`e2ff`): `16.0 GT/s x16` current, `32.0 GT/s x16` max
- The immediate downstream Intel bridge and B70 GPU endpoint report a suspiciously low link:
  - `0000:22:01.0 -> 0000:23:00.0`: `2.5 GT/s x1` current and max
  - `0000:26:01.0 -> 0000:27:00.0`: `2.5 GT/s x1` current and max
  - `0000:42:01.0 -> 0000:43:00.0`: `2.5 GT/s x1` current and max
  - `0000:46:01.0 -> 0000:47:00.0`: `2.5 GT/s x1` current and max
- `lspci -vv` capability details require root on this machine, so this is a high-priority red flag rather than a fully proven root cause.
- Idle `xpu-smi` frequency/power is low (`400-517 MHz`, `0-2 W`) even with the model loaded, but a decode load sample showed clocks can jump to `2800 MHz` and about `110-115 W` on active devices. Low idle clocks are not by themselves the current bottleneck.

## Interpretation

Do not spend another long loop chasing sub-millisecond allocation changes until this platform issue is understood. If the final B70 endpoint really is constrained to Gen1 x1, tensor-parallel collectives, host dispatch, model loading, and any PCIe fallback path are all operating with a severe handicap. If this is only a sysfs reporting artifact for the B70 internal bridge, we still need root `lspci -vv` confirmation so future performance claims are credible.

The current `~99 tok/s` single-request result remains valid as a measured endpoint result, but the hardware may not be configured close to its ceiling.

## Follow-up actions

1. Get root-level PCIe capability output:
   - `sudo lspci -vv -s 23:00.0`
   - repeat for `27:00.0`, `43:00.0`, `47:00.0`, and the `e2ff/e2f0` bridge devices.
2. Validate BIOS/platform settings:
   - Above 4G decoding enabled.
   - ReBAR enabled.
   - Slot bifurcation is not forcing x1 downstream links.
   - PCIe generation is not forced to Gen1.
   - Any onboard PCIe switch/retimer firmware or board setting is current.
3. Test root-only reversible runtime policies before another benchmark:
   - Set PCIe ASPM policy to `performance`.
   - Set B70 endpoint and bridge `power/control` to `on`.
   - Use `sudo scripts/tune-b70-runtime-performance-policy.sh --apply` for the reversible sysfs writes; the script is dry-run by default.
   - Re-run `scripts/audit-b70-host-links.sh`.
   - Re-run p512/n512 r4 direct speed and a frontdoor exact-OK smoke.
4. If link state still reports `2.5 GT/s x1`, plan a cold-boot/BIOS/slot validation before deeper kernel work.

## Production note

The accepted launcher is still useful and the service is healthy, but production setup should include this host-link audit as a preflight. A production deployment that silently boots with low PCIe link state will make software tuning results misleading.
