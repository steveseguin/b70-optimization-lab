#!/usr/bin/env bash
# Fetch the exact model bytes a packet was measured against, from the publisher at an immutable
# revision. The repository and revision come from the recipe manifest, so this cannot quietly fetch a
# different build, and every file the manifest pins is fetched - including the configuration files,
# without which the directory will not load. Nothing is redistributed by this project.
#   MODEL_DIR       destination directory (required)
#   MODEL_MANIFEST  the recipe manifest (required)
# Re-running is safe: files already the right size are skipped, and verify.sh is the final word.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
manifest=${MODEL_MANIFEST:?set MODEL_MANIFEST}
dest=${MODEL_DIR:?set MODEL_DIR to the destination directory}
[[ -f "${manifest}" ]] || { echo "manifest not found: ${manifest}" >&2; exit 1; }

read -r hf_repo revision < <(python3 -c "
import json
m=json.load(open('${manifest}'))
print(m['repository'], m['revision'])
")
echo "repository ${hf_repo}"; echo "revision   ${revision}"; echo "dest       ${dest}"
mkdir -p "${dest}"

mapfile -t rows < <(python3 -c "
import json
m=json.load(open('${manifest}'))
for group in ('lfs_files','small_files'):
    for f in m.get(group) or []:
        print(f\"{f['path']}\t{f.get('bytes','')}\")
")
(( ${#rows[@]} )) || { echo "manifest lists no files" >&2; exit 1; }

# HTTP/1.1 on purpose: the HTTP/2 + xet path stalled repeatedly on this lab's link.
for row in "${rows[@]}"; do
  path=${row%%$'\t'*}; want=${row##*$'\t'}
  out="${dest}/${path}"; mkdir -p "$(dirname -- "${out}")"
  if [[ -f "${out}" && -n "${want}" && "$(stat -c%s "${out}")" == "${want}" ]]; then
    printf '  have  %s\n' "${path}"; continue
  fi
  url="https://huggingface.co/${hf_repo}/resolve/${revision}/${path}"
  printf '  get   %s\n' "${path}"
  if command -v aria2c >/dev/null 2>&1 && [[ -n "${want}" && "${want}" -gt 104857600 ]]; then
    aria2c --quiet --http-accept-gzip=false --max-connection-per-server=16 --split=16 --min-split-size=1M \
           --continue=true --auto-file-renaming=false --allow-overwrite=true \
           --dir "$(dirname -- "${out}")" --out "$(basename -- "${out}")" \
           ${HF_TOKEN:+--header="Authorization: Bearer ${HF_TOKEN}"} "${url}"
  else
    curl -fsSL --http1.1 --retry 5 --retry-delay 5 --retry-all-errors \
         ${HF_TOKEN:+-H "Authorization: Bearer ${HF_TOKEN}"} -o "${out}" "${url}"
  fi
done
echo; echo "downloaded; now verify the bytes with the packet's verify.sh"
