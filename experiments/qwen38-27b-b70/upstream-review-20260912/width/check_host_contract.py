#!/usr/bin/env python3
"""Compile exact upstream host width checks with CPU-only tensor shape stubs.

No torch, XPU initialization, model load, or kernel execution. Downloads pinned
public source into a temporary directory, verifies hashes, applies candidate.
This proves host shape rejection and kernel launch-width selection only.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "source-manifest.json").read_text())


def extract(source, name):
    if name == "interface":
        start = (
            source.index("  TORCH_CHECK(spec_token ==")
            if "  TORCH_CHECK(spec_token ==" in source
            else source.index("  // A dynamic schedule")
        )
        end = source.index("\n\n", start)
        return source[start:end]
    start = source.index(
        "  int num_spec_tokens = 0;",
        source.index(
            "const int " + ("num_virtual_tokens" if name == "conv" else "total_seqlen")
        ),
    )
    end = source.index("\n  }", start) + len("\n  }")
    return source[start:end] + "\n return num_spec_tokens;"


def run(tree, label):
    src = tree / "csrc/xpu/gdn_attn"
    pieces = {
        key: extract((src / name).read_text(), key)
        for key, name in [
            ("conv", "causal_conv1d.hpp"),
            ("delta", "gated_delta_rule.hpp"),
            ("interface", "gdn_attn_interface.cpp"),
        ]
    }
    code = r"""
#include <stdexcept>
#include <iostream>
#define TORCH_CHECK(condition, ...) if (!(condition)) throw std::runtime_error(#condition)
struct Shape {int n,k; int dim()const{return 2;} int size(int d)const{return d?k:n;} int stride(int)const{return k;}};
"""
    for key in ["conv", "delta"]:
        code += (
            "int "
            + key
            + "(int n,int rows,int capacity) {\n const bool is_spec=true; int num_spec_decodes=n; int num_virtual_tokens=rows; int total_seqlen=rows; Shape cache{n,capacity}, accepted{n,0}; Shape* cache_indices=&cache; Shape* num_accepted_tokens=&accepted;\n"
            + pieces[key]
            + "\n}\n"
        )
    code += (
        "void interface(int n,int rows,int capacity){ int num_spec_decodes=n,spec_token=rows,num_speculative_tokens=capacity-1;\n"
        + pieces["interface"]
        + "\n}\n"
    )
    code += r"""
int main(){
 int cases[][3]={{1,3,3},{2,4,3},{2,6,3},{2,8,3},{2,5,3},{1,0,3}};
 for(auto &c:cases){
  std::cout<<c[0]<<","<<c[1]<<","<<c[2]<<":";
  try{interface(c[0],c[1],c[2]); std::cout<<"accept";}catch(const std::exception&){std::cout<<"reject";}
  for(auto fn:{conv,delta})try{std::cout<<":"<<fn(c[0],c[1],c[2]);}catch(const std::exception&){std::cout<<"reject";}
  std::cout<<"\n";
 }
}
"""
    cpp = tree / "host.cpp"
    cpp.write_text(code)
    exe = tree / "host"
    subprocess.run(["g++", "-std=c++17", str(cpp), "-o", str(exe)], check=True)
    out = subprocess.check_output([str(exe)], text=True)
    print(label + "\n" + out, end="")
    return out


def main():
    with tempfile.TemporaryDirectory(prefix="gdn-width-review-") as tmp:
        tree = Path(tmp)
        for rel, sha in MANIFEST["files"].items():
            data = urllib.request.urlopen(
                "https://raw.githubusercontent.com/vllm-project/vllm-xpu-kernels/"
                + MANIFEST["kernel_commit"]
                + "/"
                + rel
            ).read()
            assert hashlib.sha256(data).hexdigest() == sha, rel
            p = tree / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        old = run(tree, "UPSTREAM")
        assert "2,4,3:reject:3:3" in old
        subprocess.run(
            ["git", "apply", "--check", str(ROOT / "active-width-candidate.patch")],
            cwd=tree,
            check=True,
        )
        subprocess.run(
            ["git", "apply", str(ROOT / "active-width-candidate.patch")],
            cwd=tree,
            check=True,
        )
        new = run(tree, "CANDIDATE")
        assert "2,4,3:accept:2:2" in new
        assert "2,6,3:accept:3:3" in new
        for prefix in ["2,8,3", "2,5,3", "1,0,3"]:
            assert prefix + ":reject:reject:reject" in new
        print("PASS: source-pinned host checks; device behavior untested.")


if __name__ == "__main__":
    main()
