"""Generate only credited literal format tables, never kernel code."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[2] / 'stage1/packet1b/loaders'

def render():
    lines=['#pragma once', '#include <cstdint>', '// Normative GGUF tables: see ../README.md and stage1/packet1b/loaders/FORMAT.md.',
           '// Copyright ggml/llama.cpp contributors; MIT, FORMAT-DATA-LICENSE.txt.', 'namespace iq3 {']
    for filename,name,key,bits in [('iq3-grid.json','iq3_grid','packed_u32_le',32),('iq2-s-grid.json','iq2_s_grid','packed_u64_le',64),('iq3-s-grid.json','iq3_s_grid','packed_u32_le',32)]:
        values=json.loads((SOURCE/filename).read_text())[key]
        lines.append(f'inline constexpr uint{bits}_t {name}[] = {{')
        for i in range(0,len(values),4):
            lines.append('  '+','.join(hex(v)+('ull' if bits==64 else 'u') for v in values[i:i+4])+',')
        lines.append('};')
    return '\n'.join(lines+['}', ''])
if __name__=='__main__':
    (HERE/'grids.hpp').write_text(render())
