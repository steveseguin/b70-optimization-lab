# Build and develop the Own Xe engine on another computer

Start here for source development, including the planned DeepSeek V4.1 Flash
adapter. The current executable implements the SC117/Qwen family. DeepSeek
support is not implemented; its [onboarding plan](planning/deepseek-v41-onboarding.md)
identifies the new operators, model metadata and reference gates it needs.
The requested first target is an Unsloth Dynamic 3.0 GGUF used with llama.cpp;
the exact quantization file/revision is still to be pinned. Dynamic 3.0 names
the quantization generation, not a uniform tensor bit width.

You can compile the engine and run the CPU tests without model weights or an
available GPU. Executing inference additionally needs supported Intel hardware,
its runtime/driver, authenticated model files and a qualified model adapter.
The existing backend is Linux SYCL/Level Zero; CUDA, Metal and Windows are not
implemented backends. Build success does not establish model correctness.

## Get the maintained source

Use Git for development so changes can return to the shared repository. This
sparse checkout avoids downloading the lab's large historical result trees:

```bash
git clone --filter=blob:none --sparse https://github.com/steveseguin/b70-optimization-lab.git
cd b70-optimization-lab
git sparse-checkout set experiments/own-xpu-runtime/engine experiments/own-xpu-runtime/gsq-rco-iq3s/integration/host-support
git rev-parse HEAD
```

The root README, LICENSE and AGENTS.md are included by Git's cone-mode sparse
checkout. Work on `main` in this workspace. Commit focused paths and synchronize
before pushing; never overwrite the other computer's work with a force push.
Historical lab commands are evidence, not instructions to restart services or
change host power/memory settings on the new machine.

A standalone source archive is an alternative for an offline build. Extract it
and use `own-xpu-runtime-source` as the engine directory below. It includes the
source license, this guide, model profiles, CPU tests and build inputs. Its
`SOURCE-MANIFEST.json` identifies the source commit and every payload hash.
It has no Git history, model weights, compiled engine or installed libraries.
The full Git repository retains research patches, measurements and service
integration outside the archive's engine scope.

## Install build prerequisites

The observed build platform is Linux x86-64, Python 3.12 and Intel oneAPI
DPC++/C++ **2026.0.0**, with GNU C++20 headers, OpenSSL development libraries
and Level Zero headers/loader. The Python build and selected CPU tests use the
standard library; no PyTorch or model download is needed.

Use Intel's [compiler distribution](https://www.intel.com/content/www/us/en/developer/tools/oneapi/dpc-compiler-download.html)
for the matching version. On Debian/Ubuntu, the supporting packages are
`git python3 build-essential libssl-dev libze-dev`. Install these through the
destination machine's package manager; this guide does not install drivers.
For later device work, use Intel's
[GPU installation documentation](https://dgpu-docs.intel.com/installation-guides/index.html).
A different compiler/runtime version needs its own validation.

## Run the CPU gates and compile

From the repository root, set an absolute engine path. For an extracted archive,
set `OWNRT_ENGINE` to its absolute `own-xpu-runtime-source` directory instead.
Choose a fresh, durable output directory outside the source tree.

```bash
OWNRT_ENGINE="$PWD/experiments/own-xpu-runtime/engine"
OWNRT_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx
OWNRT_BUILD="$HOME/ownrt-build-20261108"

"$OWNRT_COMPILER" --version
python3 -B -m unittest discover -s "$OWNRT_ENGINE/release" -p 'test_source_bundle.py'
python3 -B -m unittest discover -s "$OWNRT_ENGINE/deployment" -p 'test_prepare.py'
python3 -B -m unittest discover -s "$OWNRT_ENGINE/deployment" -p 'test_launch_plan.py'
python3 -B -m unittest discover -s "$OWNRT_ENGINE/planning" -p 'test_placement.py'

test ! -e "$OWNRT_BUILD" && python3 -B "$OWNRT_ENGINE/build.py" "$OWNRT_BUILD" \
  --compiler "$OWNRT_COMPILER" --jobs 1 --name own-engine
```

The builder compiles and links; it never executes the resulting engine. Start
with one compiler worker and increase only with sufficient RAM. For a B70 AOT
build, add `--aot-target intel_gpu_bmg_g31` to both the initial build command and
its recorded recipe; the builder applies it at compile and link. The default
build retains the existing JIT path. This guide's build check is not a GPU test.

Keep `build-receipt.json`: it hashes the compiled dependencies, objects, binary
and runtime asset, and records compiler commands. Keep the source at its build
location: native code reads RoPE assets relative to the compiled source path.
Copying the executable alone is insufficient. Inspect linked dependencies with
`readelf -d "$OWNRT_BUILD/own-engine"` before attempting runtime setup.

Canonical SC117 source still contains the lab's model binding. For an actual
SC117 inference run on another machine, follow
[deployment/README.md](deployment/README.md) to authenticate local weights and
build with a generated binding. That binding tool deliberately rejects
DeepSeek; changing its architecture string does not implement support.

## Where to make changes

- [build.py](build.py) and [build-manifest.json](build-manifest.json): translation
  units, compile/link flags and build receipts. The manifest's historical
  consolidation hashes are not current source hashes; use the build receipt.
- [src/stage2/packet194-expert-diet-engine](src/stage2/packet194-expert-diet-engine):
  current tuned kernel families and dispatch. Preserve their existing callers.
- [src/pipeline](src/pipeline): stage layouts, transport, ownership and rollback.
- [planning](planning): CPU placement and scheduling models and their tests.
- [profiles](profiles) and [deployment](deployment): immutable model identity,
  local file binding and launch policy, currently restricted to SC117.
- [Reusable onboarding audit](planning/reusable-onboarding-audit.md): remaining
  shape, format, memory and topology assumptions. Its dated qualification
  summary is historical; source and current receipts establish today's state.

Develop DeepSeek as a separately admitted model family. First pin its exact
release and tensor formats, then implement a reference-checked text-only
autoregressive path. Add speculation and vision after that path works. Do not
substitute the old vLLM DeepSeek V4 checkpoint or its measurements for V4.1.
Preserve SC117 regression fixtures while adding the new family's tests.
