#!/usr/bin/env bash
set -euo pipefail
set -o noclobber

REPO='/home/steve/llm-optimizations'
LANE="$REPO/experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST="$LANE/data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2-prereg.json"
R1_RUNNER="$LANE/scripts/run-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.sh"
R1_MANIFEST="$LANE/data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-prereg.json"
R1_VALIDATOR="$LANE/scripts/validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.py"
R1_NOTE="$LANE/notes/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-preregistration.md"
R1_FAILURE="$LANE/data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1-failure.json"
R1_FAILURE_NOTE="$LANE/notes/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1-failure.md"
R1_TERMINAL='/mnt/fast-ai/bench-results/qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1/terminal-receipt.json'
R2_VALIDATOR="$LANE/scripts/validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2.py"
QUALITY_PYTHON='/home/steve/.venvs/vllm-xpu/bin/python'
CAMPAIGN_ID='qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r2'
ACK="RUN $CAMPAIGN_ID"
MODE='plan'
PROVIDED_ACK=''
transformed=''

while (($#)); do
  case "$1" in
    --check) MODE='check'; shift ;;
    --execute) MODE='execute'; shift ;;
    --ack) PROVIDED_ACK="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

sha_check() {
  local expected="$1" path="$2"
  [[ -f "$path" ]] || { echo "missing: $path" >&2; exit 2; }
  [[ "$(sha256sum "$path" | awk '{print $1}')" == "$expected" ]] || {
    echo "checksum mismatch: $path" >&2
    exit 2
  }
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [[ -n "$transformed" && -e "$transformed" ]]; then
    unlink "$transformed" || rc=2
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

sha_check efe0ec09e2f50f8953b66eee0a43e0ab58240a2e79cd5a47f36674bed4041d5d "$R1_RUNNER"
sha_check 8c47322d82e866f1e4d4eb11ab7b431bc38eceb6bc894b7dc2d589c02fcb60f7 "$R1_MANIFEST"
sha_check 1a9040cfdf3cffed1d147fbdb59585cea56a3daa37806277d913d3d6dcc60e9e "$R1_VALIDATOR"
sha_check 7dd3f7ca1e8ba1d4d18f148215a6eb527eb141e1dce8dca66d4548b3791a4ba6 "$R1_NOTE"
sha_check e14754b4a121e24eab2e51cb1496feade401459b1dff92b086a38e1fd0578686 "$R1_FAILURE"
sha_check ea72d37838e3f84e8d66fadb0e6a5f5b37bfc3b0a61fe8e46c55052b16130692 "$R1_FAILURE_NOTE"
sha_check 4287e36e2eed1faabcb4e8838f6df80ea6b0b0dc14067d6f83235c72dd2079df "$R1_TERMINAL"
sha_check 202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8 "$QUALITY_PYTHON"
sha_check 357c89e2054aa169364236533fd419951dc3948290100a8837e89868a3d82617 /home/steve/.venvs/vllm-xpu/pyvenv.cfg
sha_check 422eeb712bb92b9265261ad894ef621675610f6c05c0c68f94723e4e8e67d84f /home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/transformers-5.10.2.dist-info/METADATA
sha_check 15a5ddaf489f592b77e0a934c0eeb46b51130a94064ca129232afdb0a3868efc /home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/tokenizers-0.22.2.dist-info/METADATA
sha_check 6002f29765e5bc1a3be4a1b92ed56b64968a0fecba73e7f81cd536d0c40f4fa3 /home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/numpy-2.3.5.dist-info/METADATA

python3 -B - "$R2_VALIDATOR" "$MANIFEST" <<'PY'
import importlib.util
import pathlib
import sys

spec = importlib.util.spec_from_file_location("qwen36_mtp1_parent_r2_preflight", sys.argv[1])
if spec is None or spec.loader is None:
    raise SystemExit("cannot import R2 validator")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.load_overlay(pathlib.Path(sys.argv[2]))
PY

R2_QUALITY_CAPABILITY_JSON="$("$QUALITY_PYTHON" -I -B - "$MANIFEST" <<'PY'
import hashlib
import importlib.metadata as md
import json
import pathlib
import platform
import sys

import numpy
import tokenizers
import transformers

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = manifest["quality_environment"]
probe = expected["offline_tokenizer_probe"]

def metadata_row(name):
    distribution = md.distribution(name)
    path = pathlib.Path(distribution._path) / "METADATA"
    return {
        "version": distribution.version,
        "metadata": str(path),
        "metadata_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }

tokenizer = transformers.AutoTokenizer.from_pretrained(
    probe["tokenizer_path"], trust_remote_code=True, local_files_only=True
)
token_ids = tokenizer.encode(probe["text"], add_special_tokens=False)
token_ids_sha256 = hashlib.sha256(
    json.dumps(token_ids, separators=(",", ":")).encode("utf-8")
).hexdigest()
actual = {
    "interpreter": sys.executable,
    "interpreter_realpath": str(pathlib.Path(sys.executable).resolve()),
    "interpreter_sha256": hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest(),
    "sys_prefix": sys.prefix,
    "python_version": platform.python_version(),
    "pyvenv_cfg": {
        "path": expected["pyvenv_cfg"],
        "sha256": hashlib.sha256(
            pathlib.Path(expected["pyvenv_cfg"]).read_bytes()
        ).hexdigest(),
    },
    "transformers": metadata_row("transformers"),
    "tokenizers": metadata_row("tokenizers"),
    "numpy": metadata_row("numpy"),
    "offline_tokenizer_probe": {
        "tokenizer_path": probe["tokenizer_path"],
        "text": probe["text"],
        "tokenizer_class": type(tokenizer).__name__,
        "token_ids": token_ids,
        "token_ids_sha256": token_ids_sha256,
        "local_files_only": True,
    },
}
comparison = {
    "interpreter": expected["interpreter"],
    "interpreter_realpath": expected["interpreter_realpath"],
    "interpreter_sha256": expected["interpreter_sha256"],
    "sys_prefix": expected["sys_prefix"],
    "python_version": expected["python_version"],
    "pyvenv_cfg": {
        "path": expected["pyvenv_cfg"],
        "sha256": expected["pyvenv_cfg_sha256"],
    },
    "transformers": expected["transformers"],
    "tokenizers": expected["tokenizers"],
    "numpy": expected["numpy"],
    "offline_tokenizer_probe": expected["offline_tokenizer_probe"],
}
if actual != comparison:
    raise SystemExit("quality interpreter capability drift")
print(json.dumps(actual, separators=(",", ":"), sort_keys=True))
PY
)"
export R2_QUALITY_CAPABILITY_JSON

transformed="$(mktemp /tmp/qwen36-mtp1-parent-r2.XXXXXX.sh)"
python3 -B - "$R1_RUNNER" "$transformed" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
replacements = (
    ("qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1", "qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r2", 2),
    ("2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-prereg.json", "2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2-prereg.json", 1),
    ("validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.py", "validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2.py", 1),
    ('QUALITY_CLIENT="$REPO/scripts/qwen36-text-quality-suite.py"', 'QUALITY_CLIENT="$REPO/scripts/qwen36-text-quality-suite.py"\nQUALITY_PYTHON="/home/steve/.venvs/vllm-xpu/bin/python"', 1),
    ('python3 -B "$QUALITY_CLIENT"', '"$QUALITY_PYTHON" -I -B "$QUALITY_CLIENT"', 1),
    ('> "$RUN_ROOT/candidate-mtp1/quality.stdout.json"', '> "$RUN_ROOT/candidate-mtp1/quality.stdout.json" 2> "$RUN_ROOT/candidate-mtp1/quality.stderr.log"', 1),
    ("qwen36-q4km-mtp1-parent-r1", "qwen36-q4km-mtp1-parent-r2", 1),
    ('echo "fixture_sha256=$(sha256sum "$FIXTURE" | awk \'{print $1}\')"', 'echo "fixture_sha256=$(sha256sum "$FIXTURE" | awk \'{print $1}\')"\n  echo "r2_run_root=$RUN_ROOT"\n  echo "quality_environment=$R2_QUALITY_CAPABILITY_JSON"\n  echo "transformed_runner_sha256=$R2_TRANSFORMED_RUNNER_SHA256"', 1),
)
for old, new, count in replacements:
    actual = source.count(old)
    if actual != count:
        raise SystemExit(f"frozen R1 transform count drift for {old!r}: {actual} != {count}")
    source = source.replace(old, new)
path = pathlib.Path(sys.argv[2])
path.write_text(source, encoding="utf-8")
path.chmod(0o700)
PY
R2_TRANSFORMED_RUNNER_SHA256="$(sha256sum "$transformed" | awk '{print $1}')"
[[ "$R2_TRANSFORMED_RUNNER_SHA256" == 21b12584dc1e10b3d8483de23ce6f149979eecf5f71313c54f511a7bc2be639a ]] || {
  echo "transformed R2 runner checksum drift: $R2_TRANSFORMED_RUNNER_SHA256" >&2
  exit 2
}
export R2_TRANSFORMED_RUNNER_SHA256

if [[ "$MODE" != execute ]]; then
  python3 -B - "$MODE" "$ACK" "$R2_TRANSFORMED_RUNNER_SHA256" "$R2_QUALITY_CAPABILITY_JSON" <<'PY'
import json, sys
print(json.dumps({
    "schema": "neural.download.qwen36-llama-mtp1-parent-sentinel-r2-plan.v1",
    "mode": sys.argv[1],
    "default_is_inert": True,
    "exact_ack": sys.argv[2],
    "transformed_runner_sha256": sys.argv[3],
    "quality_environment": json.loads(sys.argv[4]),
}, indent=2, sort_keys=True))
PY
  exit 0
fi

[[ "$PROVIDED_ACK" == "$ACK" ]] || { echo 'exact --ack required' >&2; exit 2; }
bash "$transformed" --ack "$ACK"
