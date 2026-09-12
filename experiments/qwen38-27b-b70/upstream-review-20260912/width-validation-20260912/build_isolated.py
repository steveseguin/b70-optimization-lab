#!/usr/bin/env python3
"""Build two exact spec entrypoints, no full vLLM/TLA/oneDNN build or install."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def function(source, name):
    token = name + "("
    start = source.index(token)
    start = source.rfind("\n", 0, start) + 1
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--patch", type=Path)
    p.add_argument("--compiler", default="/opt/intel/oneapi/compiler/2025.3/bin/icpx")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    src = args.output / "src"
    shutil.copytree(args.source / "csrc/xpu/gdn_attn", src / "csrc/xpu/gdn_attn")
    shutil.copy(args.source / "csrc/dispatch_utils.h", src / "csrc/dispatch_utils.h")
    if args.patch:
        subprocess.run(
            ["git", "apply", "--check", str(args.patch.resolve())], cwd=src, check=True
        )
        subprocess.run(["git", "apply", str(args.patch.resolve())], cwd=src, check=True)
    source = (src / "csrc/xpu/gdn_attn/gdn_attn_interface.cpp").read_text()
    # Exact upstream queue adapter; architecture helpers are unused by spec ops.
    utils = (args.source / "csrc/utils.h").read_text()
    adapter = function(utils, "vllmGetQueue")
    text = (
        """#include <sycl/sycl.hpp>
#include <torch/all.h>
#include <torch/library.h>
#include <c10/xpu/XPUStream.h>
#include "dispatch_utils.h"
#include "causal_conv1d.hpp"
#include "gated_delta_rule.hpp"
namespace vllm { namespace xpu {
"""
        + adapter
        + "\n}}\n"
    )
    text += function(source, "causal_conv1d_spec") + "\n"
    text += function(source, "gated_delta_rule_spec") + "\n"
    text += """TORCH_LIBRARY(width_review, m) {
 m.def("conv", TORCH_FN(causal_conv1d_spec));
 m.def("delta", TORCH_FN(gated_delta_rule_spec));
}
"""
    tu = args.output / "isolated.cpp"
    tu.write_text(text)
    import torch
    from torch.utils.cpp_extension import include_paths, library_paths

    cmd = [
        args.compiler,
        "-std=c++17",
        "-O2",
        "-shared",
        "-fPIC",
        "-fsycl",
        "-fsycl-max-parallel-link-jobs=2",
        "-Wno-deprecated-declarations",
        "-D_GLIBCXX_USE_CXX11_ABI=" + str(int(torch._C._GLIBCXX_USE_CXX11_ABI)),
        str(tu),
    ]
    for path in include_paths() + [str(src / "csrc"), str(src / "csrc/xpu/gdn_attn")]:
        cmd += ["-I", path]
    for path in library_paths():
        cmd += ["-L", path, "-Wl,-rpath," + path]
    cmd += [
        "-ltorch",
        "-ltorch_cpu",
        "-ltorch_xpu",
        "-lc10",
        "-lc10_xpu",
        "-o",
        str(args.output / "width_review.so"),
    ]
    (args.output / "build-command.json").write_text(json.dumps(cmd, indent=2) + "\n")
    env = dict(os.environ, MAX_JOBS="2")
    subprocess.run(cmd, env=env, check=True)
    lib = args.output / "width_review.so"
    (args.output / "build-result.json").write_text(
        json.dumps(
            {
                "torch": torch.__version__,
                "library_sha256": hashlib.sha256(lib.read_bytes()).hexdigest(),
                "patch": str(args.patch),
                "scope": "spec-only; exact queue adapter; no GPU execution",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
