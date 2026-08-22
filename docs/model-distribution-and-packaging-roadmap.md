# Model Distribution And Packaging Roadmap

The project should make verified B70 work easy to consume without turning the
repository into an unlicensed weight mirror or flattening research evidence
into unsupported one-click claims. The package is the tested recipe, patches,
configuration, validation evidence, and download automation. Model weights
continue to come from their licensed publisher at an immutable revision unless
the license is explicitly reviewed for redistribution.

## Audience Tracks

### New users with one or two GPUs

A promoted starter packet should ask only for the model, GPU count, storage
location, and service port. It should then:

1. inspect Intel GPU count, VRAM, driver, PCIe link, RAM, and free storage;
2. select only a verified one- or two-card profile;
3. fetch exact model bytes from the publisher and verify them;
4. use a digest-pinned runtime or build a pinned source commit plus patch;
5. run a short health and quality gate before reporting success;
6. print the local OpenAI-compatible URL and a copy-ready client example;
7. save an environment/result packet that can be attached to an issue.

No automatic hardware guess should silently change quantization, KV precision,
context, cache policy, or speculative decoding. Those choices change quality
or comparability and must remain visible.

The first starter targets should be deliberately modest:

- one B70: Ornith 1.5 9B Q8 and LFM2.5 2.6B Q8 after bring-up;
- one or two B70s: Ornith 1.5 35B Q4 after quality qualification;
- existing promoted lanes: use their current `repro/` packets until they are
  wrapped by the same interface.

### Advanced contributors

Contributors should be able to submit a patch, recipe, or result packet without
losing recognition or bypassing verification. The existing `community/`
boundary remains correct. Recognition is attached to what was contributed:

- the contributor and source PR are retained in `community/<entry>/STATUS.md`;
- an adopted patch is credited by exact commit/digest at the point it is used;
- the matched local A/B and quality result state what the patch changed;
- a promoted scoreboard/result row names the contributor when their concrete
  delta is part of that row;
- a report that only identifies a model or inspires a test is acknowledged as
  an intake lead, not credited with unrelated lab-developed optimizations.

This gives useful work durable recognition while keeping the repository's own
measurements and recipes authoritative.

## Package Levels

| Level | Deliverable | Promotion gate |
| --- | --- | --- |
| 0 | Model-intake catalog entry | Revision, size, checksum, license state, fit rationale |
| 1 | Native Linux `repro/` packet | Clean install, fixed quality gate, exact source/patch identity |
| 2 | Linux container packet | Digest-pinned image, Intel device mapping, persistent model/cache volumes, one/two-GPU profiles, same native quality result |
| 3 | Windows preview packet | PowerShell preflight/download/verify plus WSL2, Docker Desktop, or native llama.cpp path; explicitly unverified until run on Windows hardware |
| 4 | Windows-qualified packet | Fresh Windows machine replay, driver/runtime identity, quality/performance evidence, recovery instructions |

## Container Direction

Start containers with models that already have a strong native repro. A
container packet should contain:

```text
packages/<model>-b70/
  README.md
  package.json
  compose.yaml
  env/one-gpu.env
  env/two-gpu.env
  scripts/preflight.sh
  scripts/download-model.sh
  scripts/verify.sh
  scripts/smoke-test.sh
```

Images must be pinned by digest, not a floating tag. Model directories and Hugging
Face caches are read-only in the serving container. GPU devices are explicit.
The packet records whether the image contains project patches or applies a
source patch during a reproducible build. A container result is not assumed to
match a native result until the fixed suite is replayed in the container.

## Windows Direction

Do not promise a native Windows experience before the test machine exists.
Prepare portable pieces now:

- a PowerShell equivalent of model download, byte-count, and SHA-256 checks;
- path handling that supports NTFS and spaces without hard-coded `/home` or
  `/mnt` locations;
- a hardware/driver report command that users can attach to submissions;
- Docker Desktop/WSL2 instructions where Intel XPU pass-through is actually
  supported and tested;
- a native llama.cpp/SYCL packet where the Windows toolchain is reproducible.

The first Windows release should be labelled preview and should favor a small
single-card model. Performance numbers remain Linux-only until the same gate is
run on the Windows host.

## Automation Order

1. Finish the revision-pinned USB intake queue and re-inventory the drive.
2. Establish clean one-card baselines for the two small starter models.
3. Define `package.json` from a proven `repro/` packet rather than inventing a
   separate configuration authority.
4. Ship one digest-pinned Linux container and replay its quality gate.
5. Add two-GPU selection only after device/topology checks are reliable.
6. Build the Windows preview on the future test machine and promote it only
   after fresh-install evidence exists.

