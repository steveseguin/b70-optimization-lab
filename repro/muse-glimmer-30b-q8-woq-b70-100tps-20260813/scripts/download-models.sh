#!/usr/bin/env bash
set -euo pipefail

destination=${1:-"$PWD/muse-models"}
source_root=${LLAMA_CPP_ROOT:-"$HOME/src/llama.cpp-muse-q8-woq-repro"}
target_revision=faa5b025c584459c13febfa5c59883516710ae39
assistant_revision=e8192f3a8f617f74be2ce220360c89ef4789f39f
metadata_revision=a4e59da52a7bc87ae7251dd5545c0dd437c44b68
target_name=Muse-Glimmer-30B-UD-Q8_K_XL.gguf
target_sha=e63bf23b7710ecdea2579e4b1de58980c4a2b446e8ecf48b782cfcefd2e31770
draft_sha=4a624b08e65047d94768f9ada606a1c42a1a7c08e05fc1ed0be876f1606b2ab2

mkdir -p "$destination"
if [[ -z ${HF_TOKEN:-} && -r "$HOME/.config/huggingface/token" ]]; then
    HF_TOKEN=$(<"$HOME/.config/huggingface/token")
    export HF_TOKEN
fi
command -v hf >/dev/null || {
    echo "install the Hugging Face CLI first: python3 -m pip install huggingface_hub" >&2
    exit 2
}

target_url="https://huggingface.co/unsloth/Muse-Glimmer-30B-GGUF/resolve/$target_revision/$target_name"
curl --fail --location --continue-at - --output "$destination/$target_name" "$target_url"
printf '%s  %s\n' "$target_sha" "$destination/$target_name" | sha256sum -c -

hf download meta-models/Muse-Glimmer-30B-assistant \
    --revision "$assistant_revision" --local-dir "$destination/assistant-hf"
hf download meta-models/Muse-Glimmer-30B \
    --revision "$metadata_revision" --local-dir "$destination/target-metadata" \
    --include '*.json' '*.model' '*.txt' 'tokenizer*' 'merges.txt' 'vocab*'

python3 "$source_root/convert_hf_to_gguf.py" "$destination/assistant-hf" \
    --outfile "$destination/dflash-bf16.gguf" --outtype bf16 \
    --target-model-dir "$destination/target-metadata"

if ! printf '%s  %s\n' "$draft_sha" "$destination/dflash-bf16.gguf" | sha256sum -c -; then
    cat >&2 <<'EOF'
The original assistant download-time revisions and complete input hashes were
not retained. The current observed repository pins did not reconstruct the
record GGUF byte-for-byte. Obtain the hash-pinned dflash-bf16.gguf from the
record operator or treat this as a new model identity and rerun every gate.
EOF
    exit 3
fi
echo "models verified in $destination"
