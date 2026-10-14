# CPU qualification and retention

Run from the repository root, in the inherited CPU affinity. No command below
runs an accelerator program. At most two compiler jobs and four CPU workers may
run together; the retained campaign runs two host ranks and monitors their summed
anonymous memory. Mini gates stop at 8 GB; real gates stop at 9 GB with no
concurrent heavy job, leaving at least 1 GB below the user's 10 GB ceiling.
Transport also retains its stricter 8 GiB combined-child guard; each process has
an 8 GB address-space limit. The first guard reached ends the CPU case. Do not run model gates alongside
a memory-heavy compile. Each producer checks root free space before writing,
refuses below8GB plus its reserve, and keeps this packet's build below3GB.

Use `nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B` for every Python
command below, with `P=experiments/own-xpu-runtime/stage2/packet45-merged3` as a
shell variable. All native children inherit the same priority and affinity.

1. `$P/build.py prepare` creates hash-bound local input bundles and arithmetic
   fixtures from the existing official/approved model files. It does not download
   weights. `$P/draft_baseline.py --prepare` freezes historical oracle bytes;
   those bytes are references, never a packet45 pass.
2. `$P/build.py gnu-host --jobs 2`, then `icpx-host`, `asan`, and `device` with
   the same job limit. Device mode compiles and links only. Never execute any
   program beneath `build/device` during CPU preparation.
3. `$P/build_native_controller.py` and `$P/native_controller_gate.py` for the
   normal, ASAN/UBSAN and TSAN binaries qualify the transport state machine.
   The matching `native-mailbox-fault-*` host binaries check dead/malformed
   peers and repeated-request wakeups.
4. `$P/cpu_merged_gate.py` runs79 fresh mini-model cases: all capacities, both
   placements/controllers, wrong guesses, late draft failure, suppression,
   cancellation, EOS, fresh-process repeats and terminal boundaries32/64.
   `$P/cpu_real_gate.py` runs six native first-eight-token checks of the first
   fixed suite prompt (both placements at every capacity). This is a correctness
   subset, never a complete suite or performance result. The32,768/rank1 case
   goes first to expose the largest modeled anonymous-memory peak early.
5. `$P/capacity_selection_gate.py`, `$P/capacity_fixture_gate.py`, and
   `$P/capacity_draft_gate.py --run` check capacity geometry, actual merged
   kernels and draft bytes against references with GNU and Intel host compilers.
   The p39 helper has56 actual owner-submit versus unfused-chain checks.
6. `$P/cpu_gates.py` checks 18 owner/lifetime suites;
   `$P/asan_fixture_gate.py` checks maximum-capacity arithmetic under ASAN/UBSAN.
   `$P/wrapper_cpu_gate.py` runs the wrapper tests. Every window is mocked at
   every capacity and draft placement; suite windows additionally cover32,
   64 and128-token manifests. No mocked timing or success is device evidence.
7. `$P/test_real_cross_placement_gate.py` runs 11 focused tamper checks.
   After real6 completes, `$P/real_cross_placement_gate.py` compares draft guesses,
   same-capacity state and 17 fixed-size semantic outputs across capacities.
   It makes no cross-capacity raw cache-prefix claim.
   `$P/test_seal45_bindings.py` checks 45 seal binding and tamper cases.
   `$P/build.py seal` calls `seal45.py`. It requires the current binary/source
   identities and every declared gate; a partial campaign cannot pass. It writes
   `build-receipt.json`, `cpu-tests.json` and `BINARY-HASHES.md`.

CPU scratch is hashed and receipted, then immediately archived and deleted.
Compressed archives retain metadata/events and original raw fixture hashes;
large scratch model bytes are reproducible, not silently treated as retained.
K1 fixture output blobs are separately compressed and hash-verified. KD creates
its own fresh selected-dispatch CPU reference at window time. Ignored binaries
are rebuilt from the source closure and mode receipts; their hashes are sealed.

The full32/64/128-token real suites, fresh-owner device repeats, actual memory
census and the end-to-end benefit of rank0 drafting remain coordinator gates.

After sealing, `test_window_seal_admission.py` runs the real admission code with
all launchers blocked. Run `seal45.verify_window_admission()` from the packet
Python import directory to create `window-seal-binding.json`. It binds the exact
unchanged build receipt to the successful rehearsal; it does not rewrite the
seal it tested. Finally run `merge_inventory.py` to bind the complete packet.


## HC repair qualification

Run `$P/hc_activation_gate.py --label after` before sealing. It compiles only
host executables and checks all four real HC adapter scenarios plus every BF16
NaN payload under six compiler settings. The frozen `before.json` is negative
evidence, not a current gate. Case 53 is error=7; case 54 is payload `0x7fc1`.

`$P/hc_fix_campaign.py builds`, `gates`, `models`, then `final` reproduce the
repair campaign serially (two compile jobs maximum). Device mode only compiles
and links. The final phase seals and rehearses admission with launchers blocked.
Logs and stage receipts live in `evidence/hc-activation-fix/`. Commands in
`WINDOW.md` and `coordinator_windows.sh` remain unchanged, but a new seal needs
fresh device chains.

## Sequential-owner gate repair

`sequential_owner_campaign.py all` reruns the complete CPU qualification and
reseals without rebuilding or executing device artifacts. It includes fresh
capacity fixture arms (`capacity_fixture_gate.py --fresh`), both host compilers,
ASAN, HC compiler checks, owner/controller gates, 79 miniature cases, six real
model cases, draft captures, seal tests and blocked-launch admission. It runs
serially under the same nice/ionice/OMP limits above. Logs and the prior seal
are retained in `evidence/sequential-owner-fix/`.

`wrapper_cpu_gate.py` now also runs `coordinator_cpu_gate.py`. The latter invokes
the exact, unchanged `coordinator_windows.sh` for all nine windows at
4096/rank0, 4096/rank1 and 32768/rank0. Its test-only shell prefix interception
routes the script's actual window arguments into `window.main(cpu_rehearsal=True)`.
It uses private miniature inputs and a host-only pre-seal identity, with mocked
hardware admission. All fixture, prerequisite, summary and retention gates run.
The device path cannot consume these rehearsal receipts. K0 is a structural
shim; K1/K2 use host validation mode; K2 must fail device timing while passing a
separate exact event-structure gate. The miniature suites are correctness and
orchestration checks, not model speed results.

The seal requires the complete retained three-chain matrix within its existing
wrapper receipts. `full_wrapper_gate.py` delegates to this maintained rehearsal;
its inherited packet40 harness is no longer an alternative way to qualify the
merged wrapper. After final sealing, `sequential_owner_summary.py` verifies all
41 artifacts, all source/gate bindings, the three-chain archive, the detached
admission binding and the preserved coordinator history.
