#!/usr/bin/env python3
"""Create the D (original-FP8 draft experts) source copies on top of the a-reset-stream service sources.

Default behaviour (--draft-experts int8) is unchanged; --draft-experts fp8 keeps the official E4M3 codes and
their BF16 128x128 block scales and decodes them exactly in F32 inside the draft expert kernel.
"""
import difflib, hashlib, json, sys
from pathlib import Path

R = Path('/home/steve/llm-optimizations')
L = R / 'experiments/own-xpu-runtime/gsq-rco-iq3s'
OUT = L / 'service-speed/d-mtp-fp8'
X = 'experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s'
NAT = X + '/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine'
A = 'experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/source/'
FILES = {  # repo-relative original path -> source to copy from (a-reset-stream copy if one exists)
    X + '/dense-packed-block/engine/build/source/entry.cpp': A + X + '/dense-packed-block/engine/build/source/entry.cpp',
    X + '/dense-packed-block/engine/build/source/main.cpp': A + X + '/dense-packed-block/engine/build/source/main.cpp',
    X + '/integration/build/private/source/diet-native/native-src/mtp.hpp': X + '/integration/build/private/source/diet-native/native-src/mtp.hpp',
    NAT + '/p59_draft.hpp': NAT + '/p59_draft.hpp',
    NAT + '/mtp_kernels.hpp': NAT + '/mtp_kernels.hpp',
    NAT + '/p59_hc.hpp': NAT + '/p59_hc.hpp',  # includes p59_draft.hpp (rebind only)
    NAT + '/p83_head.hpp': NAT + '/p83_head.hpp',  # includes p59_draft.hpp (rebind only)
    NAT + '/mtp_kernels.cpp': NAT + '/mtp_kernels.cpp',
}
def sha(b): return hashlib.sha256(b).hexdigest()
def copy_path(rel): return OUT / 'source' / rel

def sub(text, old, new, count=1):
    if text.count(old) != count:
        sys.exit(f'patch anchor count {text.count(old)} != {count}: {old[:90]!r}')
    return text.replace(old, new)

PATCHES = {}
PATCHES['main.cpp'] = [
    ('  bool reset_dump=true,finish_dump=true,token_stream=false;\n',
     '  bool reset_dump=true,finish_dump=true,token_stream=false;\n'
     '  // Draft-only weight format; target arithmetic is untouched. Default keeps the executed INT8 requantization.\n'
     '  bool draft_experts_fp8=false;\n'),
    ('    else if (k == "--token-stream") {\n',
     '    else if (k == "--draft-experts") {\n'
     '      auto v=value();require(v=="int8"||v=="fp8","draft experts must be int8 or fp8");\n'
     '      a.draft_experts_fp8=v=="fp8";\n'
     '    }\n'
     '    else if (k == "--token-stream") {\n'),
]
PATCHES['mtp_kernels.hpp'] = [
    ('bool int8=false,paired=false;', 'bool int8=false,paired=false,fp8=false;'),
]
PATCHES['mtp.hpp'] = [
    # exact canonical dequantization layout: E4M3 codes + F32-widened BF16 block scales per 128 columns
    ('inline std::string official(const std::string& n){',
     'inline std::vector<uint8_t> fp8_pack(const std::vector<uint8_t>& w,const std::vector<uint8_t>& sc,unsigned rows,unsigned cols){\n'
     ' // Row = cols E4M3 codes, then cols/128 F32 scales (exact widening of the checkpoint BF16 block scale).\n'
     ' require(w.size()==size_t(rows)*cols&&rows%128==0&&cols%128==0&&sc.size()==size_t(rows/128)*(cols/128)*2,"draft FP8/scales shape");\n'
     ' size_t rb=cols+cols/128*4;std::vector<uint8_t> out(size_t(rows)*rb);\n'
     ' for(unsigned r=0;r<rows;++r){std::memcpy(out.data()+size_t(r)*rb,w.data()+size_t(r)*cols,cols);\n'
     '  for(unsigned k=0;k<cols;++k)require((w[size_t(r)*cols+k]&127)!=127,"nonfinite official draft FP8");\n'
     '  for(unsigned b=0;b<cols/128;++b){size_t si=((r/128)*(cols/128)+b)*2;uint16_t bits=uint16_t(sc[si])|(uint16_t(sc[si+1])<<8);uint32_t f=uint32_t(bits)<<16;float scale=iq3::bits_float(f);require(std::isfinite(scale)&&scale>=0,"draft FP8 scale");std::memcpy(out.data()+size_t(r)*rb+cols+b*4,&f,4);}\n'
     ' }return out;\n'
     '}\n'
     'inline std::string official(const std::string& n){'),
    ('unsigned rows{},cols{},experts=1;bool int8=false;};', 'unsigned rows{},cols{},experts=1;bool int8=false,fp8=false;};'),
    ('w.int8=routed&&!e.a.mini;', 'w.fp8=routed&&!e.a.mini&&e.a.draft_experts_fp8;w.int8=routed&&!e.a.mini&&!w.fp8;'),
    ('size_t rb=w.int8?cols+cols/16*4:cols*(gain?4:2);', 'size_t rb=w.int8?cols+cols/16*4:w.fp8?cols+cols/128*4:cols*(gain?4:2);'),
    ('raw=requant(store->read(prefix+".weight"),store->read(prefix+".weight_scale_inv"),rows,cols);',
     'raw=(w.fp8?fp8_pack:requant)(store->read(prefix+".weight"),store->read(prefix+".weight_scale_inv"),rows,cols);'),
    # p59 fused path (not selected in the service) has no FP8 kernel: refuse rather than misread bytes.
    ('a.experts=w.experts;a.int8=w.int8;\n  if(l.op=="routed_gemv"||l.op=="expert_gate_up"){a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);if(l.op=="expert_gate_up"){a.paired=true;a.peer=weights.at(l.weights[1]).id;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}}\n  if(l.label.ends_with(".low")',
     'a.experts=w.experts;a.int8=w.int8;require(!w.fp8,"p59 draft path has no FP8 expert kernel");\n  if(l.op=="routed_gemv"||l.op=="expert_gate_up"){a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);if(l.op=="expert_gate_up"){a.paired=true;a.peer=weights.at(l.weights[1]).id;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}}\n  if(l.label.ends_with(".low")'),
    ('a.experts=w.experts;a.int8=w.int8;\n  if(l.op=="routed_gemv"||l.op=="expert_gate_up"){a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);if(l.op=="expert_gate_up"){a.paired=true;a.peer=weights.at(l.weights[1]).id;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}}\n  e.finish(0,mtp36::linear',
     'a.experts=w.experts;a.int8=w.int8;a.fp8=w.fp8;\n  if(l.op=="routed_gemv"||l.op=="expert_gate_up"){a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);if(l.op=="expert_gate_up"){a.paired=true;a.peer=weights.at(l.weights[1]).id;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}}\n  e.finish(0,mtp36::linear'),
]
PATCHES['mtp_kernels.cpp'] = [
    # F: 0 = BF16 (unchanged), 1 = INT8 (unchanged), 2 = FP8 codes + F32 block scales.
    ('template<unsigned K,bool Int8> inline float lane(const uint8_t* w,const uint16_t* x,unsigned l){\n if constexpr(!Int8)return p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);\n else {',
     'inline float fp8_value(uint8_t b){\n'
     ' // Exact E4M3 (bias 7) decode by bit construction; NaN codes were refused at load.\n'
     ' uint32_t e=(b>>3)&15,m=b&7;\n'
     ' float x=e?iq3::bits_float(((e+120)<<23)|(m<<20)):float(m)*0x1p-9f;\n'
     ' return b&128?-x:x; // negation is exact, including signed zero\n'
     '}\n'
     'template<unsigned K,unsigned F> inline float lane(const uint8_t* w,const uint16_t* x,unsigned l){\n if constexpr(F==0)return p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);\n'
     ' else if constexpr(F==2){float sum=0;for(unsigned tile=l*8;tile<K;tile+=256)for(unsigned k=tile;k<std::min(tile+8,K);++k){\n'
     '  const auto* s=w+K+(k/128)*4;uint32_t u=uint32_t(s[0])|(uint32_t(s[1])<<8)|(uint32_t(s[2])<<16)|(uint32_t(s[3])<<24);\n'
     '  float value=iq3::bits_float(u)*fp8_value(w[k]);float product=value*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;}return sum;}\n'
     ' else {'),
    ('template<unsigned K,bool Int8,bool Pair> struct Dense final:', 'template<unsigned K,unsigned F,bool Pair> struct Dense final:'),
    ('static constexpr size_t rb=Int8?K+4*((K+15)/16):K*2;', 'static constexpr size_t rb=F==1?K+4*((K+15)/16):F==2?K+4*(K/128):K*2;'),
    ('lane<K,Int8>(b.w+off,x,l)', 'lane<K,F>(b.w+off,x,l)', 2),
    ('lane<K,Int8>(b.peer+off,x,l)', 'lane<K,F>(b.peer+off,x,l)', 2),
    ('template<unsigned K,bool I,bool Pair> Launch issue(ownrt::Device& d,const Linear& a){Dense<K,I,Pair> op;',
     'template<unsigned K,unsigned I,bool Pair> Launch issue(ownrt::Device& d,const Linear& a){Dense<K,I,Pair> op;'),
    ('template<unsigned K> Launch typed(ownrt::Device& d,const Linear& a){if(a.int8)return a.paired?issue<K,true,true>(d,a):issue<K,true,false>(d,a);return a.paired?issue<K,false,true>(d,a):issue<K,false,false>(d,a);}',
     'template<unsigned K> Launch typed(ownrt::Device& d,const Linear& a){if(a.int8)return a.paired?issue<K,1,true>(d,a):issue<K,1,false>(d,a);\n'
     ' if(a.fp8){if constexpr(K%128==0)return a.paired?issue<K,2,true>(d,a):issue<K,2,false>(d,a);else throw std::invalid_argument("draft FP8 needs K%128==0");}\n'
     ' return a.paired?issue<K,0,true>(d,a):issue<K,0,false>(d,a);}'),
    (' if(!a.rows||!a.batch||a.batch>10||', ' if(a.int8&&a.fp8)throw std::invalid_argument("draft linear format");\n if(!a.rows||!a.batch||a.batch>10||'),
    (' size_t rb=a.int8?a.columns+4*((a.columns+15)/16):a.columns*2;', ' size_t rb=a.int8?a.columns+4*((a.columns+15)/16):a.fp8?a.columns+4*(a.columns/128):a.columns*2;'),
]
manifest = []
originals = {}
for rel, src in FILES.items():
    originals[rel] = (R / src).read_bytes()
# rebind absolute includes to the copies (exact strings of the original absolute paths and the a-reset copies)
rebind = {}
for rel, src in FILES.items():
    rebind[str(R / rel)] = str(copy_path(rel))
    rebind[str(R / src)] = str(copy_path(rel))
for rel, src in FILES.items():
    text = originals[rel].decode()
    for old, new in rebind.items():
        text = text.replace('#include "' + old + '"', '#include "' + new + '"')
    name = Path(rel).name
    for p in PATCHES.get(name, []):
        old, new = p[0], p[1]
        text = sub(text, old, new, p[2] if len(p) > 2 else 1)
    dst = copy_path(rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)
    diff = ''.join(difflib.unified_diff(originals[rel].decode().splitlines(True), text.splitlines(True), 'a/' + src, 'b/' + rel))
    (OUT / 'patches').mkdir(exist_ok=True)
    (OUT / 'patches' / (name + '.patch')).write_text(diff)
    manifest.append(dict(original=rel, copied_from=src, copy=str(dst.relative_to(OUT)), from_sha256=sha(originals[rel]), patched_sha256=sha(text.encode())))
(OUT / 'source-manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
print(json.dumps([(Path(m['original']).name, m['patched_sha256'][:12]) for m in manifest]))
