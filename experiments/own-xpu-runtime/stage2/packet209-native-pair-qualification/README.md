# P209: one synthetic native pair qualification, prepared but not admitted

P209 adds an explicitly guarded entry and one-shot coordinator around the unchanged [P208 native fixture](../packet208-sycl-paired-projections/native_fixture.cpp). It has compiled successfully. No P209 executable has been invoked, no device has been enumerated, and no GPU correctness or performance result exists.

The current target is **not available**: the root coordinator's passive inventory found that the protected vision application holds BDF `0000:27:00.0` as well as another card. See [root admission disposition](evidence/root-admission-disposition.json). The daily applications, both PAUSE files, queues and device settings remain untouched. No operational manifest is issued by these preparation tools.

## Compiled identity

[build_entry.py](build_entry.py) copies P208's compiled fixture object through `objcopy --redefine-sym main=p208_compile_only_main`, compiles only the new entry, and links the same 33 inherited native objects. Offline extraction verifies the renamed object's device image is byte-identical to P208: SHA256 `e90834e35401eceaa48d1cb9691b6b0bfa56d456e9d57464636140d0c2e3f4a5`, 7,008 bytes. The linked fixture and both host entry symbols are present. [Build receipt](evidence/build-compile-only.json) retains commands, source/object identities, dependency closure, per-attempt source snapshots and logs. These checks do not execute or load the artifact.

The unchanged fixture uses one native Device owner for Q6_K K2560/variant6/split1/stride3380 shapes 10240 and 6144. It compares both paired outputs with selected native `p33.dense.segment` and independent CPU arithmetic, then exercises live-input and shared-weight controls. All transfers complete before subsequent compute/readback. Four-byte pair workspace handles are ABI bindings, not an arithmetic scratch-use claim. This is an exactness fixture, with no model payload, timing or throughput claim.

## Admission and ownership

[ADMISSION.md](ADMISSION.md) defines the fixed manifest and future unit recipe. Python checks complete source closure, exact binary, current boot/fault review, all four cards' passive node/dev_t/BDF mapping, protected PID/starttick identities, target descriptor vacancy, resource floors, queue/latch bytes and one-shot unit properties. No card ordinal or historical `card1` node name is an identity authority.

The admitted native child checks its closed environment, unlimited address space, priority/affinity, umask, parent identity, manifest and live heartbeat before enumeration. It requires one filtered Level Zero GPU with exact BDF27. It then opens an explicit read-only admission render descriptor and checks its character-device `dev_t` against the manifest and sysfs. Parent ACK confirms this child's identity and **admission descriptor**, not an already-created runtime backend. Only then can the unchanged P208 fixture create its owner. The descriptor remains held until safe fixture return; a retained fixture never reaches descriptor destruction.

Reservation A uses the existing exact-screen lane-A policy, with the existing DrainPermit. Both flocks remain held through uncertain child/spawn/drain states. One incident SIGTERM at most; passive diagnosis continues after a fault without admitting new work. A failed but proven exited/safe/descriptor-empty process may release flocks while failed durable markers remain. Success requires the native owner idle/teardown receipt, observed child, process exit0, exact two-case result and a complete passive target-empty scan. Descriptor emptiness alone is not proof of physical GPU quiescence. No restart, retry, service stop, restore, hard kill or automatic stale-marker cleanup exists.

## Resource scope

The two cases retain 56,578,064 device-allocation bytes and a 1,048,576-byte pinned transfer slab in one owner. Synthetic host vectors peak around 69.3 MB before compiler/driver overhead. Admission forecasts 3 GiB host headroom and 256 MiB root writes above a 27,000,000,000-byte floor. Driver/JIT/cache and diagnostics remain a monitored forecast, not a hard aggregate bound or a free-VRAM measurement. The inherited device capacity check reports total capacity, not observed free VRAM.

`HOME` remains `/home/steve`. Supported `SYCL_CACHE_DIR`, `NEO_CACHE_DIR` and `XDG_CACHE_HOME` point to new private control/cache directories; no cache enable/disable toggle or cache drop is used. The installed SYCL/Level Zero library strings expose these path variables. Parent journal/process/sysfs checks are passive. A 90-second native heartbeat budget covers bounded passive command/scan latency; expiry halts new fixture requests. This is not a native execution deadline or a kill timeout.

## CPU preparation

The build runs nice19 on helper cores8–15,24–31, OMP/BLAS/MKL2, under the shared compile lock and a compiler-only 4 GiB AS limit. That compiler limit must never propagate to the future native owner. Python guard tests use synthetic records and temporary real flock contexts; they never instantiate a native backend. The native `--guard-check` mode is static-manifest-only and exits before live-entry checks or enumeration; it has not been invoked as part of the compile-only build.

All 25 [CPU guard tests](evidence/guard-tests.json) pass, including the observed occupied-target refusal. Independent review repeats the same tests. This tests the Python validators and injected process boundaries; the native guard remains source/build reviewed only.

Each build attempt retains its complete `nm -C --defined-only` symbol inventory, approximately 5 MB, beside the exact source snapshot and receipt. The two logs describe different entry builds and support offline linkage review. Keep them with their attempt receipts; reconstructing either inventory requires that attempt's exact ELF and the recorded inspection command. Compiled objects and binaries remain local ignored artifacts, so the inventories preserve review evidence when those build products are unavailable.
