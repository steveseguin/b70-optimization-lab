#!/usr/bin/env python3
"""CPU-only ABI identity screen; copy accepted kernels only after exact matches.

No model code, torch import, device access, image pull, or server action. Images
must already exist locally. A mismatch requires a rebuild in the new base.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

OLD = "ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2"
NEW = "vllm/vllm-openai-xpu@sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41"
SCREEN = r'''
import hashlib, json, pathlib
root=pathlib.Path('/opt/venv/lib/python3.12/site-packages')
torch=root/'torch'
files=[torch/'version.py']+list(torch.glob('_C*.so'))+list((torch/'lib').glob('*.so*'))
required=['libtorch_cpu.so','libtorch_python.so','libc10.so','libtorch_xpu.so']
assert all((torch/'lib'/name).is_file() for name in required)
assert list(torch.glob('_C*.so'))
result={}
for p in sorted(set(files)):
 if not p.is_file(): continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 result[str(p.relative_to(root))]=h.hexdigest()
# Native dependencies outside torch can affect kernel ABI too. Resolve their
# actual loaded-library search paths with ldd, without importing torch.
import subprocess, os
env=dict(os.environ)
env['LD_LIBRARY_PATH']=str(torch/'lib')+':'+env.get('LD_LIBRARY_PATH','')
text=subprocess.check_output(['ldd',str(root/'vllm_xpu_kernels/_xpu_C.abi3.so')],text=True,env=env)
assert 'not found' not in text,text
for line in text.splitlines():
 if '=>' not in line:continue
 soname,tail=line.split('=>',1);path=tail.strip().split()[0]
 if not path.startswith('/'):continue
 if any(key in soname for key in ('sycl','stdc++','gcc_s','ze_loader','ur_loader')):
  p=pathlib.Path(path);h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
  result['external/'+soname.strip()]=h.hexdigest()
print(json.dumps(result,sort_keys=True))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    identities = {}
    for label, image in (("accepted", OLD), ("new_base", NEW)):
        inspected = json.loads(subprocess.check_output(["docker", "image", "inspect", image]))[0]
        hashes = json.loads(subprocess.check_output([
            "docker", "run", "--rm", "--network", "none", "--memory", "512m",
            "--entrypoint", "/opt/venv/bin/python", image, "-c", SCREEN,
        ], text=True))
        identities[label] = {"image": image, "image_id": inspected["Id"], "hashes": hashes}
    equal = identities["accepted"]["hashes"] == identities["new_base"]["hashes"]
    receipt = {"torch_and_native_dependency_hashes_equal": equal, "identities": identities,
               "kernel_source": "6d92b1bfbf32767ecda8e819613eb151e70030ad",
               "onednn_source": "0e2a5bfeef1bfbffc3137464606540233086ce9b",
               "accepted_patches": ["r137a", "r137b", "r221"],
               "runtime_quality_and_performance_qualification": "still required"}
    (args.output / "kernel-reuse-identity.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if not equal:
        raise SystemExit("ABI identity differs: do not reuse; rebuild in the new base.")
    container = subprocess.check_output(["docker", "create", "--entrypoint", "/bin/true", OLD], text=True).strip()
    try:
        hashes = {}
        expected = dict(line.split() for line in (Path(__file__).parent / "../rebase-v0290/kernel-artifacts.sha256").read_text().splitlines())
        expected_by_name = {Path(path).name: sha for sha, path in expected.items()}
        for name in ("_xpu_C.abi3.so", "libgdn_attn_kernels_xe_2.so"):
            destination = args.output / name
            subprocess.run(["docker", "cp", container + ":/opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/" + name, str(destination)], check=True)
            hashes[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
            assert hashes[name] == expected_by_name[name], (name, hashes[name])
        receipt["kernel_artifact_sha256"] = hashes
        (args.output / "kernel-reuse-identity.json").write_text(json.dumps(receipt, indent=2) + "\n")
    finally:
        subprocess.run(["docker", "rm", container], check=True)
    print("Accepted kernel artifacts copied after exact ABI identity comparison:", args.output)


if __name__ == "__main__":
    main()
