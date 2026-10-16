#!/usr/bin/env python3
"""Static ELF/name-resolution review only. Never loads a native library."""
import ast
import datetime
import hashlib
import json
import re
import subprocess
from collections import deque
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
PREP = REPO / "experiments/own-xpu-runtime/stage1/packet4-prep"
OUT = Path(__file__).with_name("loader-audit.json")
forbidden = ("/home/steve/src/vllm-current-main", "/mnt/raid-models", "rescue")
def safe(path):
    s = str(path)
    if any(x in s for x in forbidden):
        raise ValueError("forbidden path; no access: " + s)
    return Path(path)
def digest(data):
    return hashlib.sha256(data).hexdigest()
def read(path):
    return safe(path).read_text()
p = json.loads(read(PREP / "driver/preregistration.json"))
prior_path = REPO / "data/2026-10-16-flash-next-a367-prep/stage-and-runtime.json"
prior = json.loads(read(prior_path))
venv = Path(p["defaults"]["python"]).parent.parent
stage = Path(prior["stage"])
compiler = Path("/opt/intel/oneapi/compiler/2025.3")
ld = [stage, venv / "lib", venv / "lib/python3.12/site-packages/torch/lib", compiler / "lib", compiler / "opt/compiler/lib"]
source_text = read(PREP / "driver/window_driver.py")
assert "'LD_LIBRARY_PATH': f'{stage}/vllm_xpu_kernels:{venv}/lib:{venv}/lib/python3.12/site-packages/torch/lib:{compiler}/lib:{compiler}/opt/compiler/lib'" in source_text
assert "compiler = '/opt/intel/oneapi/compiler/2025.3'" in source_text
assert "'PYTHONPATH': f'{HERE}:{PREP}:{stage}:{source}'" in source_text
new_source = Path("/home/steve/src/vllm-flashnext-a367-clean-20261016")
assert str(new_source) in read(PREP / "a367-calibrate/a367_calibrate_load.py")
cache_text = subprocess.check_output(["/sbin/ldconfig", "-p"], text=True)
cache = {}
for line in cache_text.splitlines():
    match = re.match(r"\s*(\S+) \(([^)]*)\) => (\S+)", line)
    if match and "x86-64" in match[2]:
        cache.setdefault(match[1], []).append(match[3])
roots = [x["path"] for x in prior["files"] if x["path"].endswith(".so")]
roots += [prior["collectives"][0]["path"], p["defaults"]["python"]]
roots += [str(x) for x in (venv/"lib/python3.12/site-packages/torch").glob("_C*.so")]
roots += [str(venv/"lib/python3.12/site-packages/torch/lib/libtorch_global_deps.so")]
objects, edges, unresolved, warnings, cwd_entries = {}, [], [], [], []
def dynamic(path):
    resolved = safe(path).resolve(); safe(resolved)
    key = str(resolved)
    if key not in objects:
        output = subprocess.check_output(["readelf", "-d", key], text=True, stderr=subprocess.STDOUT)
        fields = {tag: re.findall(r"\(" + tag + r"\).*?\[([^]]*)\]", output) for tag in ("NEEDED", "RPATH", "RUNPATH", "SONAME")}
        st = resolved.stat()
        objects[key] = {"path": key, "bytes": st.st_size, "mtime_ns": st.st_mtime_ns, "dynamic_sha256": digest(output.encode()), **fields}
    return objects[key]
def expand(values, origin):
    result=[]
    for value in values:
        for part in value.split(":"):
            part=part.replace("${ORIGIN}",str(origin)).replace("$ORIGIN",str(origin))
            if not part:
                cwd_entries.append({"origin":str(origin), "meaning":"CWD is the new calibration output; supervisor creates only receipt files and scratch/rpc before Popen; no DSOs there"}); continue
            if "$" in part or not part.startswith("/"):
                warnings.append({"origin":str(origin),"unresolved_search_token":part});continue
            safe(part); result.append(part)
    return result
queue = deque((x, ()) for x in roots)
seen = set()
while queue:
    pathname, inherited = queue.popleft()
    obj=dynamic(pathname); key=obj["path"]
    context=(key,inherited)
    if context in seen: continue
    seen.add(context)
    local_rpath = expand(obj["RPATH"],Path(key).parent) if not obj["RUNPATH"] else []
    ancestry=tuple(dict.fromkeys(local_rpath+list(inherited)))
    search=list(ancestry)+[str(x) for x in ld]+expand(obj["RUNPATH"],Path(key).parent)
    for need in obj["NEEDED"]:
        if "/" in need:
            candidates=[need] if need.startswith("/") else []
        else:
            candidates=[str(Path(x)/need) for x in search]+cache.get(need,[])+[str(Path(x)/need) for x in ("/lib/x86_64-linux-gnu","/usr/lib/x86_64-linux-gnu","/lib64","/usr/lib64")]
        found=[]
        for name in dict.fromkeys(candidates):
            path=safe(name)
            if path.is_file():
                resolved=safe(path.resolve())
                if str(resolved) not in [x["resolved"] for x in found]: found.append({"candidate":name,"resolved":str(resolved)})
        edge={"from":key,"needed":need,"selected":found[0] if found else None,"other_existing_candidates":found[1:]}
        edges.append(edge)
        if not found: unresolved.append(edge)
        else: queue.append((found[0]["candidate"],ancestry))
site=venv/"lib/python3.12/site-packages"
pth=[]
for path in sorted(site.glob("*.pth")):
    body=read(path)
    pth.append({"path":str(path),"sha256":digest(body.encode()),"text":body})
finders=[]
for path in sorted(site.glob("__editable__*vllm*finder.py")):
    body=read(path); mappings={}
    for node in ast.walk(ast.parse(body)):
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            if any(isinstance(x,ast.Name) and x.id in ("MAPPING","NAMESPACES") for x in targets):
                try: mappings[targets[0].id]=ast.literal_eval(node.value)
                except (ValueError,TypeError): pass
    finders.append({"path":str(path),"sha256":digest(body.encode()),"mapping":mappings,"text":body})
pythonpath=[str(PREP/"driver"),str(PREP),str(stage.parent),str(new_source)]
shadow=[]
for directory in pythonpath[:-1]:
    for suffix in ("vllm.py","vllm/__init__.py"):
        path=Path(directory)/suffix
        if path.is_file(): shadow.append(str(path))
source_init=new_source/"vllm/__init__.py"
source_review = {}
for relative in ("vllm/device_allocator/__init__.py", "vllm/device_allocator/xpumem.py", "vllm/v1/worker/xpu_worker.py", "vllm/v1/worker/gpu_worker.py", "vllm/config/model.py"):
    body=read(new_source/relative)
    assert digest(body.encode()) == p["source_pins"][relative]
    source_review[relative]={"sha256":digest(body.encode()),"certified_pin_matches":True}
optional_review={"scope":"Frozen xpumem sleep allocator retained, not instantiated by selected A367 calibration", "source_pins":source_review,"evidence":["config/model.py:338 enable_sleep_mode defaults False; sealed launcher has no --enable-sleep-mode", "gpu_worker.py:386-390 returns nullcontext for XPU with sleep disabled before get_mem_allocator_instance", "xpu_worker.py:186 attempts allocator module import at shutdown; xpumem.py:25-31 catches ImportError (including missing libsycl.so.9)", "xpumem.py:121 singleton instance defaults None; xpu_worker.py:188-189 only releases pools when instance exists", "No allocator, selector, wheel or library was replaced; no new SYCL search directory is proposed"],"unresolved_optional_needed":"libsycl.so.9", "other_installed_candidate_outside_launch_search":[str(x) for x in Path("/opt/intel/oneapi/compiler").glob("[0-9]*/lib/libsycl.so.9")],"decision":"Selected no-sleep path does not instantiate this optional allocator; unavailable extension import is explicitly caught. Full all-stage closure remains false; this source-based scope decision is not native ABI proof."}
torch_review={}
for relative in ("__init__.py", "xpu/__init__.py"):
    body=read(venv/"lib/python3.12/site-packages/torch"/relative)
    torch_review[relative]={"sha256":digest(body.encode()),"literal_libsycl_so_9_present":"libsycl.so.9" in body}
required_unresolved=[e for e in unresolved if not(e["from"]==str(stage/"xpumem_allocator.abi3.so") and e["needed"]=="libsycl.so.9")]
receipt={"schema":"flash-next.a367.static-loader-audit.v1","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"native_executed":False,"method":"readelf -d recursive DT_NEEDED review; ldconfig -p metadata; static .pth/finder text only; no ldd/runtime imports", "script_sha256":digest(Path(__file__).read_bytes()),"prior_stage_receipt_sha256":digest(prior_path.read_bytes()),"ld_library_path":list(map(str,ld)),"ld_preload":prior["collectives"][0]["path"],"ldconfig_metadata_sha256":digest(cache_text.encode()),"roots":roots,"objects":list(objects.values()),"edges":edges,"unresolved":unresolved,"search_warnings":warnings,"empty_runpath_entries":cwd_entries,"optional_allocator_review":optional_review,"torch_import_static_review":torch_review,"selected_path_required_unresolved":required_unresolved,"selected_path_static_needed_closure_resolved":not required_unresolved and not warnings,"object_count":len(objects),"edge_count":len(edges),"static_needed_closure_resolved":not unresolved and not warnings,"python_import":{"pythonpath":pythonpath,"pth":pth,"editable_finders":finders,"earlier_pythonpath_vllm_shadows":shadow,"new_source_init_sha256":digest(source_init.read_bytes()),"stage_package_init_sha256":digest((stage/"__init__.py").read_bytes()),"expected_source_init_sha256":p["source_pins"]["vllm/__init__.py"],"reason":"PYTHONSAFEPATH=1 and PYTHONNOUSERSITE=1; regular vllm package on explicit PYTHONPATH precedes site-added editable directories; PathFinder finds it before appended setuptools editable finder. Existing .pth files are inspected as text, never executed; old mapped source is not inspected.","static_source_precedence_passed":not shadow and digest(source_init.read_bytes())==p["source_pins"]["vllm/__init__.py"]},"limits":["Names resolved with recorded search precedence; this is not ABI/symbol/version validation, dlopen execution, device health, or a full runtime dependency certification.","Only ELF dynamic metadata is freshly read; stage/collective full-file hashes are previous prep evidence and still require launch byte checks.","DT_NEEDED excludes dynamically constructed dlopen plugin names (including SYCL/Level Zero backends). Hardware-capability alternatives and interposition/load-order effects are not executed.","RPATH inheritance is tracked per traversal; object selection remains static candidate resolution, not proof of the dynamic loader namespace."]}
OUT.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({k:receipt[k] for k in ("object_count","edge_count","static_needed_closure_resolved","unresolved","search_warnings")},indent=2))
print("receipt_sha256",digest(OUT.read_bytes()))
