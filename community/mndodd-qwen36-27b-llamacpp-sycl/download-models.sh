#!/usr/bin/env bash
set -euo pipefail

DEST_DIR=${DEST_DIR:-$PWD/qwen36-27b-q8-models}
WITH_SPEC=${WITH_SPEC:-0}

TARGET_REV=8a7ee08e8b9bfb857107ecc25a5599d2f38b76f8
DFLASH_REV=edb70860182c75bae2e25ab550b79adcfb170a32

download_checked() {
    local url=$1
    local name=$2
    local expected=$3
    local destination=$DEST_DIR/$name
    local partial=$destination.part

    if [[ -f "$destination" ]] && printf '%s  %s\n' "$expected" "$destination" | sha256sum --check --status; then
        printf 'Already verified: %s\n' "$destination"
        return
    fi

    mkdir -p "$DEST_DIR"
    curl --fail --location --retry 5 --retry-all-errors \
        --continue-at - --output "$partial" "$url"
    mv -- "$partial" "$destination"
    printf '%s  %s\n' "$expected" "$destination" | sha256sum --check
}

download_checked \
    "https://huggingface.co/ggml-org/Qwen3.6-27B-GGUF/resolve/$TARGET_REV/Qwen3.6-27B-Q8_0.gguf?download=true" \
    Qwen3.6-27B-Q8_0.gguf \
    73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9

if [[ "$WITH_SPEC" == 1 ]]; then
    download_checked \
        "https://huggingface.co/ggml-org/Qwen3.6-27B-GGUF/resolve/$TARGET_REV/mtp-Qwen3.6-27B-Q8_0.gguf?download=true" \
        mtp-Qwen3.6-27B-Q8_0.gguf \
        ad3862cef3dc6a3eaa0525a5b9b225f1c9c45b15956a8314a30cfaa0344a1e08
    download_checked \
        "https://huggingface.co/williamliao/qwen3.6-27B-DFlash-GGUF/resolve/$DFLASH_REV/Qwen3.6-27B-DFlash-Q8_0.gguf?download=true" \
        Qwen3.6-27B-DFlash-Q8_0.gguf \
        c37b84724fa58cc5c6b545d8b96f8617a8c3bd7f018bf608feef4d3460e0575e
fi

printf 'Models ready in %s\n' "$DEST_DIR"
