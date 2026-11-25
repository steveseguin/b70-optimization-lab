#!/bin/bash
# install.sh: build the tokenizer helper and copy the server and an engine build to /home/steve/inkling-serve.
#   install.sh <ink_run binary>      (e.g. the output of ../scripts/build.sh ink_run <path>)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
dst=/home/steve/inkling-serve
ref=/home/steve/inkling-work/ref-src/llama.cpp-b12588-mix-c0c3de8
gguf=/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf
mkdir -p "$dst/bin" "$dst/src" "$dst/systemd" "$dst/logs"
cp "$here"/{server.py,config.json,chat.html,README.md} "$dst/"
cp "$here/tokhelper.cpp" "$dst/src/"
cp "$here/systemd/inkling-server.service" "$dst/systemd/"
cp "$1" "$dst/bin/ink_run"
g++ -O2 -std=c++17 -I"$ref/include" -I"$ref/ggml/include" "$dst/src/tokhelper.cpp" -o "$dst/bin/tokhelper" \
    "$ref/build/src/libllama.a" "$ref/build/ggml/src/libggml.a" "$ref/build/ggml/src/libggml-cpu.a" \
    "$ref/build/ggml/src/libggml-base.a" -fopenmp -lpthread -ldl
# the chat template from the GGUF
python3 -I - "$gguf" "$dst/chat_template.jinja" <<'PY'
import struct, sys
f = open(sys.argv[1], 'rb')
_, _, _, nkv = struct.unpack('<IIQQ', f.read(24))
SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
def rs():
    n, = struct.unpack('<Q', f.read(8)); return f.read(n)
for _ in range(nkv):
    k = rs().decode(); t, = struct.unpack('<I', f.read(4))
    if k == 'tokenizer.chat_template':
        open(sys.argv[2], 'wb').write(rs()); break
    if t == 8: rs()
    elif t == 9:
        at, n = struct.unpack('<IQ', f.read(12))
        if at == 8:
            for _ in range(n): rs()
        else: f.read(SZ[at] * n)
    else: f.read(SZ[t])
PY
# pictures: Pillow in the server's Python (decoding and the reference's resize filter)
/home/steve/dsv41-serve/venv/bin/pip install -q "pillow>=10,<13"
echo "installed in $dst"
