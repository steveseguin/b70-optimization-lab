#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
worker_venv=${NEURAL_WORKER_VENV:-${HOME}/.venvs/neural-worker}
if [[ ! -x "${worker_venv}/bin/python" ]]; then
  python3 -m venv "${worker_venv}"
fi
if command -v uv >/dev/null 2>&1; then
  uv pip sync --python "${worker_venv}/bin/python" --require-hashes "${here}/requirements.lock"
else
  "${worker_venv}/bin/python" -m ensurepip
  "${worker_venv}/bin/python" -m pip install --require-hashes -r "${here}/requirements.lock"
fi
worker_image=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sandbox_image"])' "${here}/config.json")
docker pull "${worker_image}"
printf 'Ready. Run %s/neural-worker --help\n' "${here}"
