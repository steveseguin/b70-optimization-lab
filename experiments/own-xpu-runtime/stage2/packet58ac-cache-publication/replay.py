"""CPU-only saved-receipt census, source-extracted host probe and protocol proof.

Run from any directory, nice 19, affinity 8-15,24-31, python3 -B, stdin /dev/null.
Default verifies saved CPU probes and writes only this packet's analysis.json.
--measure-host rebuilds small host probes in /tmp and refreshes host-probe.json.
Never imports a model/runtime or runs the frozen packet's analyzers.
"""
import collections
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import statistics as st
import subprocess
import sys
import tarfile
import tempfile

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
S = P.parent
PIN = "efd357edc751e929553880b2638cada3fedb869d2f8584c51ce9bc2646d3ab9f"
hashes = {}


def read(path):
    data = path.read_bytes()
    hashes[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data


def obj(path):
    return json.loads(read(path))


def balanced(pairs):
    groups = collections.defaultdict(list)
    for cls, value in pairs:
        groups[cls].append(value)
    return st.median(st.median(values) for values in groups.values())


def census():
    b = S / "packet58z-onecard-record/evidence/card0-58z-a/WS128"
    summary = obj(b / "summary.json")
    window = obj(b / "window.json")
    cache = [json.loads(line) for line in read(b / "run/run/cache.jsonl").splitlines()]
    assert summary["passed"] and summary["arithmetic"] == "iq3-p49-split32-v1"
    for rel in ("summary.json", "run/run/cache.jsonl"):
        assert hashes[str((b / rel).relative_to(ROOT))] == window["native_files"][rel]
    keys = ["fill_bytes_total", "fills_total", "publication_uploads_total",
            "publication_bytes_total", "publication_host_ms_total"]
    rows, prompts, index = [], [], 0
    for request in summary["requests"]:
        assert request["passed"] and request["cached_tokens"] == 0
        folder = b / "run/run" / request["prompt_id"]
        pre = [json.loads(line) for line in read(folder / "prefill-timings.jsonl").splitlines()]
        gen = [json.loads(line) for line in read(folder / "timings.jsonl").splitlines()]
        assert len(pre) == request["prompt_tokens"] - 1 and len(gen) == 128
        selected = []
        for timing in pre + gen:
            current = cache[index]
            previous = cache[index - 1] if index else None
            index += 1
            assert current["position"] == index
            if timing["kind"] == "generated_token" and 2 <= timing["generated_index"] <= 100:
                row = {k: current[k] - previous[k] for k in keys}
                row.update(state=current["state"], prior_state=previous["state"])
                assert row["publication_bytes_total"] == row["publication_uploads_total"] * 1179648
                rows.append(row)
                selected.append(row)
        ts = request["token_timestamps"]
        prompts.append(dict(id=request["prompt_id"], cls=request["prompt_class"],
                            interval_ms=1000 * (ts[99] - ts[0]) / 99,
                            publication_ms=st.mean(r["publication_host_ms_total"] for r in selected)))
    assert index == len(cache) and len(rows) == 1188
    record = obj(S / "packet58z-onecard-record/submission/prepared-a/result.json")["primary_metric"]["value_tok_s"]
    def rate(fraction=0, fixed_cut=0):
        return balanced((p["cls"], 1000 / (p["interval_ms"] - fraction * p["publication_ms"] - fixed_cut)) for p in prompts)
    assert abs(rate() - record) < 1e-8
    out = dict(record_tok_s=record, positions=len(rows), all_positions=len(cache),
               means={k: st.mean(r[k] for r in rows) for k in keys},
               publication_count_histogram=dict(collections.Counter(r["publication_uploads_total"] for r in rows)),
               state_transitions=dict(collections.Counter(f'{r["prior_state"]}->{r["state"]}' for r in rows)),
               per_prompt=prompts,
               conditional_recovery_gain_percent={str(f):100*(rate(f)/record-1) for f in (.3,.5,.6,.7,1)},
               required_remaining_boundary_ms=.4*st.mean(r["publication_host_ms_total"] for r in rows))
    for count in sorted({r["publication_uploads_total"] for r in rows}):
        group = [r for r in rows if r["publication_uploads_total"] == count]
        out.setdefault("by_publications", {})[str(count)] = dict(n=len(group),
            publication_ms=st.mean(r["publication_host_ms_total"] for r in group),
            fills=st.mean(r["fills_total"] for r in group))
    for transition in sorted(out["state_transitions"]):
        group = [r for r in rows if f'{r["prior_state"]}->{r["state"]}' == transition]
        out.setdefault("by_transition", {})[transition] = dict(n=len(group),
            publication_ms=st.mean(r["publication_host_ms_total"] for r in group),
            fills=st.mean(r["fills_total"] for r in group),
            max_fills=max(r["fills_total"] for r in group),
            zero_fill_tokens=sum(r["fills_total"]==0 for r in group))
    return out, rate


def host_probe():
    archive = S / "packet58z-onecard-record/lineage/58x-build-source.tar.gz"
    assert hashlib.sha256(read(archive)).hexdigest() == PIN
    prefix = "experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/"
    with tarfile.open(archive) as tar:
        receipt = json.load(tar.extractfile("build-receipt.json"))
        def member(rel):
            name = prefix + rel
            raw = tar.extractfile(name).read()
            digest = hashlib.sha256(raw).hexdigest()
            assert receipt["sources"][name] == digest, name
            hashes["archive:" + name] = digest
            return raw.decode()
        main = member("build/native/main.cpp")
        cache = member("native/cache_table.hpp")
        protocol = member("native/cache_protocol.hpp")
        member("native/publish.hpp")
        member("async_source.py")
        builds = json.load(tar.extractfile("gates/evidence/build.json"))
        engine_commands = [c for c in builds["commands"] if "entry-main" in c["name"]]
    loop = next(line for line in main.splitlines() if "staging[base+id]=" in line)
    assert loop.count("p.g.experts") == 2
    tracked = cache.replace("namespace p58 {", "namespace tracked58ac {")
    for old, new in [
        ("struct Plan {", "struct Plan {\n  std::vector<uint32_t> changed;"),
        ("table[victim]=host", "p.changed.push_back(uint32_t(victim));table[victim]=host"),
        ("table[id]={gate,up,down", "p.changed.push_back(id);table[id]={gate,up,down")]:
        assert tracked.count(old) == 1
        tracked = tracked.replace(old,new)
    read(P/"host_probe.cpp")
    if "--measure-host" not in sys.argv:
        saved=obj(P/"host-probe.json")
        assert saved["schema"]=="packet58ac.host-probe.v1"
        for path, digest in saved["source_sha256"].items():
            assert hashes[path]==digest, path
        return saved["host_probes"], engine_commands
    # Observe the shared compiler admission read-only; lock only /tmp, never ops.
    path = S.parent / "ops/compile_turn.py"
    read(path)
    spec = importlib.util.spec_from_file_location("p58ac_compile_admission", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = {}
    with tempfile.TemporaryDirectory(prefix="packet58ac-host-") as tmp:
        tmp = Path(tmp)
        for name, content in {"cache_table.hpp":cache, "tracked_cache.hpp":tracked,
                              "cache_protocol.hpp":protocol, "packing_loop.inc":loop.replace("p.g.experts","512")}.items():
            (tmp/name).write_text(content)
        for tag, compiler in [("gnu", "/usr/bin/g++"), ("intel_host", "/opt/intel/oneapi/compiler/2026.0/bin/icpx")]:
            binary = tmp/tag
            cmd = [compiler, "-std=c++20", "-O3", "-march=native", "-fno-fast-math", "-ffp-contract=off",
                   "-I", str(tmp), str(P/"host_probe.cpp"), "-o", str(binary)]
            with module.LOCK.open("a+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                assert not module.active(), "Compiler/whole-host hold active; do not compile"
                compiled = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
                assert compiled.returncode == 0, compiled.stderr
            run = subprocess.run([str(binary)], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
            assert run.returncode == 0, run.stderr
            results[tag] = dict(result=json.loads(run.stdout),
                compiler_version=subprocess.check_output([compiler,"--version"], text=True).splitlines()[0],
                flags=cmd[1:6], binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    saved=dict(schema="packet58ac.host-probe.v1",host_probes=results,
               source_sha256={k:v for k,v in hashes.items() if k.startswith("archive:") or k.endswith("host_probe.cpp")},
               max_rss_kib_children=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    (P/"host-probe.json").write_text(json.dumps(saved,indent=2)+"\n")
    return results, engine_commands


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3,4*1024**3))
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32))
    assert os.readlink("/proc/self/fd/0") == "/dev/null"
    counts, rate = census()
    probes, commands = host_probe()
    diag = obj(S/"packet58y-onecard-attribution/analysis/report.json")
    read(S/"packet58y-onecard-attribution/attribution_source.py")
    diag_split = diag["measured_split"]
    # Check the diagnostic's wait sum directly against its hash-bound raw rows.
    diagnostic_rows=[]
    for path, digest in diag["sources"].items():
        if not path.endswith("/attribution.jsonl"):
            continue
        raw=read(ROOT/path)
        assert hashlib.sha256(raw).hexdigest()==digest
        diagnostic_rows.extend(json.loads(line) for line in raw.splitlines())
    diagnostic_rows=[r for r in diagnostic_rows if 2 <= r["generated_index"] <= 100]
    assert len(diagnostic_rows)==1188
    assert abs(st.mean(r["host_wait_ms"]["table_publication"] for r in diagnostic_rows)
               -diag_split["host_wait_ms"]["table_publication"])<1e-9
    timing = probes["intel_host"]["result"]["benchmarks"]
    packing = timing["full_pack_rotating_8"]["median_ms"]
    delta = timing["delta_pack_64"]["median_ms"]
    saving = packing-delta
    pub = counts["means"]["publication_host_ms_total"]
    # Device transport rates are assumptions, not measured bandwidth.
    scenarios = []
    for bandwidth in (4,8,16,25):
        byte_saving_ms=(1179648-64*40)/(bandwidth*1e6)
        net=saving+byte_saving_ms-.020
        scenarios.append(dict(assumed_H2D_GB_s=bandwidth, assumed_delta_entries=64,
                              assumed_unchanged_fixed_and_scatter_cost=True,
                              assumed_new_bookkeeping_and_apply_overhead_ms=.020,
                              saving_ms=net,recovery_fraction=net/pub,
                              gain_percent=100*(rate(fixed_cut=net)/counts["record_tok_s"]-1)))
    report=dict(schema="packet58ac.cpu-feasibility.v1",device_executed=False,model_read=False,
                decision="no_build_60pct_not_supported",census=counts,host_probes=probes,
                original_entry_compile_commands=commands,
                diagnostic_58y=dict(cache_bytes=diag["cache_bytes"],
                  publication_wait_ms=diag_split["host_wait_ms"]["table_publication"],
                  publication_wait_calls=diag_split["host_wait_calls"]["table_publication"],
                  boundary_exclusive_ms=diag_split["host_exclusive_ms"]["cache_boundary"],
                  note="Different cache/instrumented identity. Wait includes device execution and host synchronization, not pure synchronization."),
                modeled_host_only_saving_ms=saving,
                additional_device_saving_required_ms=.6*pub-saving,
                additional_device_saving_required_with_20us_overhead_ms=.6*pub-saving+.020,
                assumed_transport_scenarios=scenarios,
                max_rss_kib_self=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                max_rss_kib_probe_children=obj(P/"host-probe.json")["max_rss_kib_children"])
    read(P/"host_probe.cpp");read(P/"replay.py")
    report["inputs_sha256"]=hashes
    (P/"analysis.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("inputs_sha256","original_entry_compile_commands")},indent=2))


if __name__ == "__main__":
    main()
