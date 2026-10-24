#!/usr/bin/env python3
"""Three same-binary tiny Engine owners; HOST_ONLY indirect cache binding proof."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import struct
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
P198 = P.parent / "packet198-postreply-checkpoint"
P207 = P.parent / "packet207-host-paired-projections"
PYTHON = Path("/home/steve/.venvs/vllm-xpu/bin/python")
OUTPUT = P / "build/host-proof-a"
FLOOR = 27_000_000_000
WRITE_BOUND = 96 * 1024**2
CACHE_SCHEMA_READY = True  # Final source/build/cache receipt contract independently reviewed.
LABEL = "experimental-host-engine-cache"
CONTRACT = "v1.2+p211"
EARLY_REFUSAL = "p211 cache2 requires HOST_ONLY mini pipeline resident single-owner mode"


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def save_result(path, value, primary=None):
    try:
        write(path, value)
    except BaseException as secondary:
        if primary is None:
            raise
        print("Secondary evidence write failure: " + repr(secondary), file=sys.stderr)


def close_exited_pipes(process, primary=None):
    if process is None:
        return
    try:
        exited = process.poll() is not None
    except BaseException as secondary:
        if primary is None:
            raise
        print("Secondary owner status uncertainty; endpoints retained: " + repr(secondary), file=sys.stderr)
        return
    if exited:
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except BaseException as secondary:
                    if primary is None:
                        raise
                    print("Secondary pipe cleanup failure: " + repr(secondary), file=sys.stderr)


def client_class():
    path = ROOT / "experiments/own-xpu-runtime/integration/request_front/client_v2.py"
    spec = importlib.util.spec_from_file_location("p211_pinned_front", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    need(Path(module.__file__).resolve() == path, "transport module origin")
    return module.NativeFront


def environment():
    parent = P.parent / "packet181-session-swap-v3/one-card"
    script = """import json,sys
from pathlib import Path
p=Path(sys.argv[1]);sys.path.insert(0,str(p))
import native_env,common
assert Path(native_env.__file__).resolve()==p/'native_env.py'
assert Path(common.__file__).resolve()==p/'common.py'
print(json.dumps(native_env.environment('A')))
"""
    result = subprocess.run([str(PYTHON), "-B", "-c", script, str(parent)],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=30, check=False)
    need(result.returncode == 0, "parent environment import failed")
    env = json.loads(result.stdout)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        env[key] = "2"
    return env


def binary_plan():
    receipt = read(P / "evidence/build-compile-only.json")
    need(receipt["passed"] is True and receipt["device_executed"] is False,
         "successful CPU-only build receipt required")
    host = next(row for row in receipt["plans"] if row["target"] == "host")
    binary = Path(host["binary"])
    need(binary == P / "build/host/own-rt-iq3", "fixed host binary only")
    need(sha(binary) == host["binary_sha256"], "host binary changed")
    commands = host["commands"]
    need(any(command[0] == "/usr/bin/g++" and "-DOWN_RT_HOST_ONLY" in command
             for command in commands), "GNU HOST_ONLY compile identity")
    for name, digest in host["repository_dependencies"].items():
        need(sha(ROOT / name) == digest, "compiled source changed: " + name)
    for name, digest in host["objects"].items():
        need(sha(name) == digest, "inherited object changed")
    return host


def parent_reference():
    path = P198 / "evidence/host-probe.json"
    proof = read(path)
    need(proof["passed"] is True and proof["device_executed"] is False, "parent host proof")
    directory = Path(proof["lifecycle"]["run_directory"])
    inventory = read(P198 / "evidence/host-probe-artifacts.json")["files_sha256"]
    tokenizer = directory / "tokenizer.tsv"
    paths = [tokenizer]
    for checkpoint in ("s1", "s2", "s3", "s4", "s5", "s6"):
        folder = directory / "checkpoints" / checkpoint
        manifest = read(folder / "manifest.json")
        paths.extend([folder / "manifest.json", folder / "tokens.bin",
                      *(folder / (blob["name"] + ".bin") for blob in manifest["blobs"])])
    for item in paths:
        name = str(item.relative_to(ROOT))
        need(inventory[name] == sha(item), "retained parent artifact changed: " + name)
    return dict(receipt=str(path), receipt_sha256=sha(path), directory=str(directory),
                tokenizer=str(tokenizer), files_sha256={str(x.relative_to(ROOT)): sha(x) for x in paths})


def owner_argv(binary, run, mode):
    return [str(binary), "--mini", "--pipeline-mini", "--memory", "resident",
            "--context", "64", "--retain-steps", "none", "--native-nice", "19",
            "--seconds", "180", "--request-front", "--request-front-max-requests", "16",
            "--request-front-idle-seconds", "15", "--request-front-checkpoints", str(run / "checkpoints"),
            "--request-front-tokenizer-identity", str(run / "tokenizer.tsv"), "--output", str(run / "owner"),
            "--p211-host-cache", mode, "--p211-host-observe", "--cache-maintenance", "serial"]


def p207_reference():
    """External immutable bytes only; never restore its different binary identity."""
    proof_path = P207 / "evidence/host-proof.json"
    proof = read(proof_path)
    inventory_path = P207 / "evidence/raw-host-proof-index.json"
    inventory = read(inventory_path)
    need(proof["passed"] and not proof["device_executed"] and not proof["model_executed"],
         "P207 successful tiny host authority")
    directory = Path(inventory["source_root"])
    paths = []
    for checkpoint_id in proof["serial"]["checkpoints"]:
        prefix = Path("serial/checkpoints") / checkpoint_id
        paths.append(prefix / "manifest.json")
        paths.extend(prefix / name for name in proof["serial"]["checkpoints"][checkpoint_id]["files_sha256"])
    for relative in paths:
        item = directory / relative
        expected = inventory["files"][relative.as_posix()]
        need(item.stat().st_size == expected["bytes"] and sha(item) == expected["sha256"],
             "P207 external checkpoint changed: " + str(relative))
    return dict(receipt=str(proof_path), receipt_sha256=sha(proof_path), directory=str(directory),
                inventory_sha256=sha(inventory_path),
                files_sha256={str(directory / path): sha(directory / path) for path in paths})


def plan(output=OUTPUT):
    need(CACHE_SCHEMA_READY, "P211 cache evidence contract is not finalized; no owner launch")
    output = Path(output)
    need(output.parent == P / "build" and output.name.startswith("host-proof-"), "fixed packet scratch namespace")
    need(not os.path.lexists(output), "preserve existing output; no automatic retry")
    need(not (P / "evidence/host-proof.json").exists(), "preserve prior proof receipt")
    host = binary_plan()
    authority = read(P / "authority-inputs.json")
    for name, digest in authority["source_sha256"].items():
        need(sha(ROOT / name) == digest, "arithmetic/parent authority changed: " + name)
    need(sha(P / "fixtures.json") == authority["expected_fixture_sha256"], "frozen fixture changed")
    need(EARLY_REFUSAL in (P / "build/native/main.cpp").read_text(), "compiled early refusal changed")
    fixtures = read(P / "fixtures.json")
    need(len(fixtures["rows"]) == 16 and fixtures["context"] == 64, "fixed fixture count/context")
    paths = [Path(__file__), P / "fixtures.json", P / "authority-inputs.json",
             ROOT / "experiments/own-xpu-runtime/integration/request_front/client_v2.py",
             P.parent / "packet181-session-swap-v3/one-card/native_env.py",
             P.parent / "packet181-session-swap-v3/one-card/common.py"]
    return dict(schema="packet211.host-proof-plan.v1", passed=True, executed=False,
                output=str(output), binary=host["binary"], binary_sha256=host["binary_sha256"],
                build_receipt_sha256=sha(P / "evidence/build-compile-only.json"),
                source_sha256={str(x.relative_to(ROOT)): sha(x) for x in paths},
                parent_reference=parent_reference(), p207_reference=p207_reference(),
                comparison_owners=3, failure_owners=1,
                total_owner_processes=4, requests_per_comparison_owner=16,
                standalone_abi_processes=1, parser_refusal_processes=10,
                saves_per_owner=13, releases_per_owner=3, context=64, vocab=16,
                disk_floor_bytes=FLOOR, planned_write_bytes=WRITE_BOUND,
                argv={name: owner_argv(host["binary"], output / name, mode)
                      for name, mode in (("direct", "off"), ("serial", "serial"), ("paired", "paired"))},
                scope="Synthetic four-layer Engine only; real CPU execution with simulated backend events; no model/GPU/serving/speed qualification")


def limits():
    need(Path(sys.executable) == PYTHON, "fixed interpreter required")
    os.sched_setaffinity(0, set(range(8, 16)) | set(range(24, 32)))
    if os.getpriority(os.PRIO_PROCESS, 0) < 19:
        os.nice(19 - os.getpriority(os.PRIO_PROCESS, 0))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))


def incident(process, receipt):
    receipt["incident_sigterm_sent"] = False
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        receipt["incident_sigterm_sent"] = True
    try:
        process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        receipt["retained_owner"] = True
        return False
    receipt["returncode"] = process.returncode
    return True


def hold_retained(process, directory, primary):
    save_result(directory / "RETAINED.json", dict(pid=process.pid, error=repr(primary),
                                                retry=False, kill=False, resource_release=False), primary)
    print("CPU owner retained; no further fixture launched: PID " + str(process.pid), flush=True)
    while True:
        try:
            if process.poll() is not None:
                return
        except BaseException:
            pass  # Status uncertainty cannot authorize closing a live endpoint.
        time.sleep(1)


def checkpoint(directory, expected_binary=None):
    manifest = read(directory / "manifest.json")
    if expected_binary:
        need(manifest["label"] == LABEL and manifest["contract"] == CONTRACT, "candidate checkpoint scope")
        need(manifest["engine"]["binary_sha256"] == expected_binary, "checkpoint binary identity")
        need(manifest["qualified_by"]["device_gates"] == [], "unexpected device qualification")
    need(len(manifest["blobs"]) == 20, "tiny checkpoint must retain all20 buffers")
    hashes = {"tokens.bin": sha(directory / "tokens.bin")}
    sizes = {"tokens.bin": (directory / "tokens.bin").stat().st_size}
    for blob in manifest["blobs"]:
        path = directory / (blob["name"] + ".bin")
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024**2,
             "bounded regular tiny blob")
        hashes[path.name] = sha(path)
        sizes[path.name] = path.stat().st_size
        need(hashes[path.name] == blob["sha256"] and sizes[path.name] == blob["bytes"], "blob extent/digest")
    need(len(hashes) == 21 and sum(sizes.values()) < 8 * 1024**2, "closed tiny state extent")
    need({x.name for x in directory.glob("*.bin")} == set(hashes), "unexpected state payload")
    state = manifest["token_state"]
    payload = (directory / "tokens.bin").read_bytes()
    tokens = list(struct.unpack("<" + "I" * (len(payload) // 4), payload))
    need(len(tokens) == state["position"] == state["length"], "processed position/history extent")
    need(state["tokens_sha256"] == hashes["tokens.bin"], "token digest")
    need(state["token_history"] == ([15, tokens[0]] if len(tokens) == 1 else tokens[-2:]), "token history")
    need((directory / "position.bin").read_bytes() == struct.pack("<I", state["position"]), "position bytes")
    need((directory / "error.bin").read_bytes() == struct.pack("<I", 0), "sticky error notclear")
    return dict(files_sha256=hashes, sizes=sizes, token_state=state,
                manifest_sha256=sha(directory / "manifest.json"))


def expected_pairs(start, count):
    out = []
    at = start
    while at < count - 1:
        width = min(2, count - 1 - at, 32 - at % 32)
        if width == 2:
            out.append(at)
        at += width
    return out


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def traces(directory, tokens, start, resumed, mode, cap, state_names):
    chunk = mode != "direct"
    rows = jsonl(directory / "prefill-chunks.jsonl")
    expected = expected_pairs(start, len(tokens)) if chunk and not resumed else []
    need([row["start"] for row in rows] == expected, "chunk coverage/finalprompt/resume boundary")
    for row in rows:
        position = row["start"] + 2
        need(row["count"] == 2 and row["layers"] == 4 and row["passed"] is True and
             row["published_position"] == position and
             row["context_extent"] == min(64, ((row["start"] + 32) // 32) * 32), "chunk trace controls")
        hashes = row["canonical_state_sha256"]
        need(set(hashes) == state_names, "chunk state inventory")
        need(all(isinstance(h, str) and len(h) == 64 and set(h) <= set("0123456789abcdef")
                 for h in hashes.values()), "chunk state digest grammar")
        for name, payload in (("position", struct.pack("<I", position)),
                              ("token", struct.pack("<i", tokens[position - 1])),
                              ("token_history", struct.pack("<qq", *tokens[position - 2:position]))):
            need(hashes[name] == hashlib.sha256(payload).hexdigest(), "chunk canonical " + name)
    generated = jsonl(directory / "timings.jsonl")
    wanted = list(range(2, cap + 2)) if resumed else list(range(1, cap + 1))
    need([row["generated_index"] for row in generated] == wanted, "final prompt/decode timing path changed")
    singles = jsonl(directory / "prefill-timings.jsonl")
    covered = {position for at in expected for position in (at, at + 1)}
    remaining = [] if resumed else [at for at in range(start, len(tokens) - 1) if at not in covered]
    timing_positions = ([] if resumed else list(range(start, len(tokens) - 1))) if mode == "serial" else remaining
    need([row["token_index"] for row in singles] == timing_positions, "actual serial-row prefill timing coverage")
    observed = jsonl(directory / "serial-prefill-state.jsonl")
    need([row["start"] for row in observed] == remaining, "serial endpoint state coverage")
    for row in observed:
        need(row["count"] == 1 and row["published_position"] == row["start"] + 1 and
             set(row["canonical_state_sha256"]) == state_names, "serial endpoint state schema")
    return dict(chunks=rows, serial_endpoints=observed,
                generated_indices=wanted, single_prefill_positions=remaining,
                actual_prefill_timing_positions=timing_positions)


def cache_evidence(directory, tokens, start, resumed, cap, mode):
    records = jsonl(directory / "cache-intervals.jsonl")
    reset_path = directory / "cache-reset.json"
    if mode == "direct":
        need(not records and not reset_path.exists(), "direct control acquired indirect cache")
        return None
    expected = []
    position = start
    if not resumed:
        while position < len(tokens) - 1:
            width = min(2, len(tokens) - 1 - position, 32 - position % 32)
            expected.append((position, width))
            position += width
    for offset in range(cap):
        expected.append((position + offset, 1))
    need([(row["start"], row["count"]) for row in records] == expected,
         "cache interval coverage omitted prefill/final/decode/restore")
    for row in records:
        need(row["frozen_table_payload"] is True, "cache bytes changed while readers owned them")
        ids = row["routes"]
        need(len(ids) == row["count"] * 4 * 10, "complete retained row/layer route inventory")
        triples = row["route_triples"]
        need(len(triples) == len(ids) and all(len(x) == 3 and all(type(v) is int and 0 <= v < 2**32 for v in x)
                                            for x in triples), "exact native Route triples")
        raw_routes = b"".join(struct.pack("<III", *triple) for triple in triples)
        need(hashlib.sha256(raw_routes).hexdigest() == row["route_sha256"], "retained route byte digest")
        for index, expert in enumerate(ids):
            layer = (index // 10) % 4
            need(type(expert) is int and 16 * layer <= expert < 16 * (layer + 1),
                 "route replay lost chronological row/layer order")
            need(triples[index][0] == expert % 16 and triples[index][1] <= 64 and
                 0 < triples[index][2] <= 64 - triples[index][1], "actual routed expert row extent")
        need(row["hits"] + row["misses"] == len(ids) and row["hits"] >= 0 and row["misses"] >= 0,
             "cache route accounting")
        need(row["publications_total"] == row["epoch"] + 1, "one publication per completed cache interval")
        for key in ("route_sha256", "normalized_table_sha256"):
            digest = row[key]
            need(type(digest) is str and len(digest) == 64 and set(digest) <= set("0123456789abcdef"),
                 "cache digest grammar")
        resident = row["resident_ids"]
        need(resident == sorted(set(resident)) and 0 < len(resident) <= 16 and
             all(type(expert) is int and 0 <= expert < 64 for expert in resident),
             "bounded actual resident expert inventory")
    reset = read(reset_path)
    need(reset["passed"] and reset["preserved"] and reset["capacity"] == 4096 and
         0 <= reset["resident_bytes"] <= 4096, "warm cache survived request reset")
    return dict(intervals=records, reset=reset)


def run_variant(spec, name, env):
    directory = Path(spec["output"]) / name
    directory.mkdir()
    (directory / "tokenizer.tsv").write_bytes(Path(spec["parent_reference"]["tokenizer"]).read_bytes())
    outcome = dict(passed=False, variant=name, rows=[], checkpoints={}, device_executed=False,
                   host_native_executed=True, incident_sigterm_sent=False, retained_owner=False)
    process = None
    primary = None
    with (directory / "stderr.log").open("wb") as log:
        try:
            process = subprocess.Popen(spec["argv"][name], env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=log)
            front = client_class()(process, context=64, vocab=16, max_requests=16,
                                   startup_timeout=30, request_timeout=30)
            outcome["ready"] = front.ready
            responses, inputs, saved_visible = {}, {}, {}
            fixture = read(P / "fixtures.json")
            for row in fixture["rows"]:
                need(shutil.disk_usage(ROOT).free >= FLOOR, "root floor during host fixture")
                tokens = row.get("tokens")
                if tokens is None:
                    prior = row["append_from"]
                    tokens = inputs[prior] + responses[prior] + row["suffix"]
                tokens = list(tokens)
                restore = row.get("restore")
                start = outcome["checkpoints"][restore]["token_state"]["position"] if restore else 0
                resumed = row.get("same_generation", False)
                response = front.request(row["id"], tokens, row["max_new"], restore=restore)
                generated = response["tokens"]
                need(len(generated) == row["max_new"], "unexpected early stop; do not weaken fixture")
                native = read(directory / "owner/requests" / row["id"] / "result.json")
                need(native["passed"] and native["tokens"] == generated and
                     native["session_reuse"] is bool(restore) and native["cached_tokens"] == start,
                     "native result/transport/restore disagreement")
                need(front.state == "awaiting-disposition", "postreply disposition lost")
                visible = (saved_visible[restore] if resumed else tokens) + generated
                if "save" in row:
                    checkpoint_id = row["save"]
                    event = front.save("save-" + row["id"], checkpoint_id, visible)
                    state = checkpoint(directory / "checkpoints" / checkpoint_id, spec["binary_sha256"])
                    need(state["manifest_sha256"] == event["manifest_sha256"], "save acknowledgement identity")
                    need(state["token_state"]["next_token"] == generated[-1], "pending token")
                    saved_visible[checkpoint_id] = visible
                    outcome["checkpoints"][checkpoint_id] = state
                else:
                    event = front.release("release-" + row["id"])
                state_names = {x[:-4] for x in outcome["checkpoints"]["s1"]["files_sha256"] if x != "tokens.bin"}
                trace = traces(directory / "owner/requests" / row["id"], tokens, start, resumed,
                               name, row["max_new"], state_names)
                pairs = paired_sites(directory, row["id"], trace, name == "paired")
                need(native["p211_cache_mode"] == ("off" if name == "direct" else name) and
                     native["p211_host_chunk2"] is (name == "paired") and
                     native["p211_chunk_count"] == len(trace["chunks"]), "native chunk reporting")
                cache = cache_evidence(directory / "owner/requests" / row["id"], tokens, start, resumed, row["max_new"], name)
                record = dict(id=row["id"], input=tokens, tokens=generated, start_position=start,
                              same_generation=resumed, control=event, trace=trace, paired_sites=pairs, cache=cache)
                outcome["rows"].append(record)
                inputs[row["id"]], responses[row["id"]] = tokens, generated
                write(directory / "progress.json", outcome)
            stopped = front.close(timeout=30)
            need(stopped["completed_requests"] == stopped["completed_controls"] == 16 and
                 stopped["reason"] == "request-limit" and not stopped["discarded_pending"] and
                 stopped["pending_request_id"] == "", "terminal protocol")
            need(process.returncode == 0, "owner exit")
            owner = read(directory / "owner/receipt.json")
            need(owner["passed"] and owner["safe_to_exit"] and owner["device_executed"] is False, "owner shutdown")
            # Engine publishes its final allocation census only at shutdown.
            # Request-time trace checks above must not read this future artifact.
            if name == "paired":
                validate_paired_census(directory, [site for row in outcome["rows"]
                                                   for site in row["paired_sites"]])
            outcome.update(passed=True, stopped=stopped, owner=owner, returncode=process.returncode)
        except BaseException as error:
            primary = error
            outcome["error"] = dict(type=type(error).__name__, message=str(error))
            if process is not None:
                try:
                    exited = incident(process, outcome)
                except BaseException as cleanup:
                    exited = False
                    outcome["cleanup_error"] = repr(cleanup)
                save_result(directory / "result.json", outcome, primary)
                if not exited:
                    hold_retained(process, directory, primary)
        finally:
            save_result(directory / "result.json", outcome, primary)
            close_exited_pipes(process, primary)
        if primary is not None:
            raise primary
    return outcome


def paired_sites(directory, request_id, trace, candidate):
    records = jsonl(directory / "owner/requests" / request_id / "paired-sites.jsonl")
    if not candidate:
        need(not records, "unpaired owner issued paired projection")
        return records
    expected = [(chunk["start"], layer, op) for chunk in trace["chunks"]
                for layer in (0, 2) for op in ("qkv", "z")]
    need([(row["start"], row["layer"], row["op"]) for row in records] == expected,
         "actual paired projection schedule differs")
    for row in records:
        need(row["captured"] is True and row["issued"] is True and
             row["skipped_original_sites"] == 2, "paired site not captured/issued or originals not skipped")
        groups = [row[key] for key in ("input_ids", "output_ids", "inject_ids", "workspace_ids")]
        need(all(len(group) == 2 for group in groups), "paired trace requires both rows")
        ids = [value for group in groups for value in group] + [row["weight_id"]]
        need(all(type(value) is int and value > 0 for value in ids) and len(ids) == len(set(ids)),
             "paired retained data aliases or invalid IDs")
    return records


def validate_paired_census(directory, records):
    """Join already checked issuance records only after successful owner exit."""
    census = read(directory / "owner/census.json")
    allocations = {row["label"]: row for row in census[0]["allocations"]}

    def allocation(label, minimum):
        row = allocations["card0:" + label]
        need(row["live"] and row["memory"] == "device" and row["bytes"] >= minimum,
             "paired allocation census extent")
        return row["id"]

    for row in records:
        need(row["captured"] is True and row["issued"] is True and
             row["skipped_original_sites"] == 2, "paired site not captured/issued or originals not skipped")
        output_slot = 2 if row["op"] == "qkv" else 3
        output_bytes = 40 if row["op"] == "qkv" else 24
        inputs = [allocation(f"p211:row{r}:retained0", 32) for r in range(2)]
        outputs = [allocation(f"p211:row{r}:retained{output_slot}", output_bytes) for r in range(2)]
        inject = [allocation(f"p211:row{r}:retained1", 8) for r in range(2)]
        workspace = [allocation(f"p211:pair-workspace{r}", 4) for r in range(2)]
        weight_name = "attn_qkv" if row["op"] == "qkv" else "attn_gate"
        weight = allocation(f"weight:blk.{row['layer']}.{weight_name}.weight", output_bytes // 2 * 16 * 4)
        need(row["input_ids"] == inputs and row["output_ids"] == outputs and
             row["inject_ids"] == inject and row["workspace_ids"] == workspace and
             row["weight_id"] == weight, "paired captured IDs do not match actual retained row allocations")
        ids = inputs + outputs + inject + workspace + [weight]
        need(len(ids) == len(set(ids)), "paired retained data aliases")


def early_refusals(spec, env):
    root = Path(spec["output"]) / "parser-refusals"
    root.mkdir()
    base = [spec["binary"], "--p211-host-cache", "paired", "--mini", "--pipeline-mini", "--memory", "resident",
            "--context", "64", "--retain-steps", "none", "--cache-maintenance", "serial"]
    cases = {"not-mini": [x for x in base if x != "--mini"],
             "not-pipeline": [x for x in base if x != "--pipeline-mini"],
             "not-resident": ["layer-streaming" if x == "resident" else x for x in base],
             "multi-card": base + ["--cards", "2"],
             "legacy": base + ["--host-path", "legacy"],
             "mtp": base + ["--draft-mtp"],
             "draft-capture": base + ["--draft-capture", str(root / "nonexistent-draft")],
             "priority-probe": base + ["--priority-probe"],
             "record": base + ["--record"],
             "oversize-context": base + ["--context", "256"]}
    records = []
    for name, argv in cases.items():
        folder = root / name
        folder.mkdir()
        output = folder / "must-not-create-owner"
        argv = argv + ["--model-dir", str(folder / "nonexistent-model"), "--output", str(output)]
        row = dict(name=name, argv=argv, passed=False, incident_sigterm_sent=False)
        with (folder / "stdout.log").open("wb") as out, (folder / "stderr.log").open("wb") as err:
            process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired as primary:
                if not incident(process, row):
                    write(folder / "result.json", row)
                    hold_retained(process, folder, primary)
                write(folder / "result.json", row)
                raise
        stderr = (folder / "stderr.log").read_text()
        row.update(returncode=process.returncode, stdout_sha256=sha(folder / "stdout.log"),
                   stderr_sha256=sha(folder / "stderr.log"), owner_output_created=output.exists())
        row["passed"] = process.returncode != 0 and EARLY_REFUSAL in stderr and not output.exists()
        write(folder / "result.json", row)
        need(row["passed"], "early chunk admission did not refuse: " + name)
        records.append(row)
    return records


def compare_states(left, right):
    need(left["files_sha256"] == right["files_sha256"] and left["sizes"] == right["sizes"], "checkpoint bytes differ")
    need(left["token_state"] == right["token_state"], "checkpoint token/control descriptor differs")


def compare(spec, direct, serial, paired):
    variants = {"direct": direct, "serial": serial, "paired": paired}
    endpoints = {}
    for name in ("serial", "paired"):
        candidate = variants[name]
        count = 0
        for left, right in zip(direct["rows"], candidate["rows"], strict=True):
            need(left["id"] == right["id"] and left["input"] == right["input"] and
                 left["tokens"] == right["tokens"], "direct/cache input/output mismatch")
            need(left["trace"]["generated_indices"] == right["trace"]["generated_indices"], "decode path changed")
            original = {row["published_position"]: row["canonical_state_sha256"]
                        for row in left["trace"]["serial_endpoints"]}
            for endpoint in right["trace"]["chunks"] + right["trace"]["serial_endpoints"]:
                need(original[endpoint["published_position"]] == endpoint["canonical_state_sha256"],
                     "cache intermediate state mismatch")
                count += 1
        need(count == 108, "all frozen2/tail endpoints required")
        endpoints[name] = count
        need(direct["checkpoints"].keys() == candidate["checkpoints"].keys(), "checkpoint inventory")
        for checkpoint_id in direct["checkpoints"]:
            compare_states(direct["checkpoints"][checkpoint_id], candidate["checkpoints"][checkpoint_id])
    paired_count = sum(len(row["paired_sites"]) for row in paired["rows"])
    skipped = sum(site["skipped_original_sites"] for row in paired["rows"] for site in row["paired_sites"])
    need(paired_count == 400 and skipped == 800, "paired arithmetic execution nonvacuity")
    need(not any(row["paired_sites"] for name in ("direct", "serial") for row in variants[name]["rows"]),
         "unpaired control executed paired arithmetic")
    need(len(serial["rows"]) == len(paired["rows"]) == 16, "cache request inventory")
    cache_counts = {}
    for name, outcome in (("serial", serial), ("paired", paired)):
        intervals = [item for row in outcome["rows"] for item in row["cache"]["intervals"]]
        need(len(intervals) == 181 and sum(item["count"] for item in intervals) == 281,
             "complete cache lifetime coverage")
        need([item["epoch"] for item in intervals] == list(range(1, 182)), "cache epochs must not reset or skip")
        need(sum(item["hits"] for item in intervals) > 0 and sum(item["misses"] for item in intervals) > 0,
             "actual resident and pinned-miss arithmetic both required")
        need(sum(item["evictions"] for item in intervals) > 0, "small cache must force eviction")
        fills = fill_bytes = 0
        previous_residents = set()
        for item in intervals:
            expected_hits = sum(expert in previous_residents for expert in item["routes"])
            need(item["hits"] == expected_hits and item["misses"] == len(item["routes"]) - expected_hits,
                 "actual frozen resident/miss classification")
            need(type(item["evictions"]) is int and 0 <= item["evictions"] <= item["fills"],
                 "cache eviction/fill accounting")
            previous_residents = set(item["resident_ids"])
            fills += item["fills"]
            fill_bytes += item["fill_bytes"]
            need(item["fills_total"] == fills and item["fill_bytes_total"] == fill_bytes,
                 "cache cumulative fill accounting")
        for previous, current in zip(outcome["rows"], outcome["rows"][1:]):
            need(previous["cache"]["intervals"][-1]["normalized_table_sha256"] ==
                 current["cache"]["reset"]["normalized_table_sha256"],
                 "warm cache changed between requests/reset")
        cache_counts[name] = dict(intervals=len(intervals), consumed_positions=281,
                                 hits=sum(item["hits"] for item in intervals),
                                 misses=sum(item["misses"] for item in intervals),
                                 evictions=sum(item["evictions"] for item in intervals),
                                 fills=fills, fill_bytes=fill_bytes)
    for left, right in zip(serial["rows"], paired["rows"], strict=True):
        need(left["cache"] == right["cache"], "serial/paired cache policy, routes or state differs")
    prior = read(spec["parent_reference"]["receipt"])["lifecycle"]
    external = read(spec["p207_reference"]["receipt"])["serial"]
    for name, result in variants.items():
        for row, old in zip(result["rows"], external["rows"], strict=True):
            need(row["id"] == old["id"] and row["input"] == old["input"] and row["tokens"] == old["tokens"],
                 "P207 external input/output differs")
        for checkpoint_id in result["checkpoints"]:
            old = checkpoint(Path(spec["p207_reference"]["directory"]) / "serial/checkpoints" / checkpoint_id)
            compare_states(result["checkpoints"][checkpoint_id], old)
        for row, old in zip(result["rows"][:8], prior["requests"]):
            need(row["id"] == old["id"] and row["tokens"] == old["tokens"], "P198 external output")
        for checkpoint_id in ("s1", "s2", "s3", "s4", "s5", "s6"):
            compare_states(result["checkpoints"][checkpoint_id],
                           checkpoint(Path(spec["parent_reference"]["directory"]) / "checkpoints" / checkpoint_id))
        for a, b in (("s3", "s4"), ("s3", "s5"), ("boundary-append", "boundary-fresh")):
            compare_states(result["checkpoints"][a], result["checkpoints"][b])
        need(result["checkpoints"]["boundary-seed"]["token_state"]["position"] == 31, "pending boundary")
        rows = {row["id"]: row for row in result["rows"]}
        need(rows["boundary-append"]["input"][31] == result["checkpoints"]["boundary-seed"]["token_state"]["next_token"],
             "restored append starts with pending token")
        need(rows["fresh-a"]["tokens"] + rows["resume-a"]["tokens"] == rows["fresh-a-reference"]["tokens"],
             "same-generation restore versus uninterrupted")
        need(rows["fresh-b"]["tokens"] == rows["final-b-release"]["tokens"], "request reset exact")
    return dict(all13_same_binary_checkpoints_exact=True, all20_blobs_plus_tokens_exact=True,
                all13_p207_external_checkpoints_exact=True, all16_p207_inputs_outputs_exact=True,
                paired_projection_sites=paired_count, original_projection_sites_skipped=skipped,
                six_parent_checkpoints_exact=True, all16_generated_sequences_exact=True,
                append_pending_31_to_32_exact=True, final_prompt_decode_resume_serial=True,
                intermediate_endpoints_exact=endpoints, matched_cache_policy_exact=True, cache_counts=cache_counts)


def validate_indirect_proof(proof):
    need(proof["schema"] == "packet211.indirect-proof.v1" and proof["passed"] is True and
         proof["device_executed"] is False and proof["model_executed"] is False and not proof["error"],
         "indirect arithmetic proof failed")
    expected_checks = {prefix + suffix for prefix in ("gate", "down") for suffix in
                       ("_capture_no_execution", "_caller_metadata_immutable",
                        "_cache_payload_consumed", "_pinned_payload_consumed")}
    faults = ("outside_first", "misaligned_first", "zero_generation_first", "outside_later")
    expected_checks |= {name + suffix for name in faults for suffix in
                        ("_output_scope", "_sticky_owner", "_failed_drained")}
    expected_checks |= {"cross_y_status_alias_refused", "cross_status_y_alias_refused",
                        "writable_input_alias_refused", "tuple_shape_refused", "short_table_extent_refused",
                        "released_pinned_capture_refused", "released_cache_capture_refused"}
    need(set(proof["checks"]) == expected_checks and all(x is True for x in proof["checks"].values()),
         "complete nonvacuous indirect binding controls")
    names = ["gate_up_valid", "gate_up_invalid", "down_valid", "down_invalid"]
    need([case["name"] for case in proof["cases"]] == names, "four direct/indirect arithmetic cases")
    for case in proof["cases"]:
        shared = case["name"].startswith("gate_up")
        invalid = case["name"].endswith("_invalid")
        need(case["passed"] is True and case["shared"] is shared and case["rows"] == 4 and
             case["columns"] == (4 if shared else 8) and case["experts"] == 4 and
             case["count"] == 10 and case["variant"] == 2 and case["captured_operations"] == 1 and
             len(case["outputs"]) == (2 if shared else 1), "actual top10 gate/up/down shape")
        for output in case["outputs"]:
            raw = bytes.fromhex(output["output_hex"])
            status = bytes.fromhex(output["status_hex"])
            need(output["bytes"] == len(raw) == 80 and len(status) == 40 and
                 hashlib.sha256(raw).hexdigest() == output["contiguous_sha256"] == output["indirect_sha256"] and
                 hashlib.sha256(status).hexdigest() == output["status_sha256"], "retained actual arithmetic bytes")
            need(struct.unpack("<10I", status) == (0, int(invalid), int(invalid), 0, 0, 0, 0, 0, 0, 0),
                 "original route status semantics")
            values = struct.unpack("<40H", raw)
            padding = range(4, 12) if invalid else (7, 10, 11)
            need(all(values[i] == 0x7fc0 for i in padding) and any(x != 0x7fc0 for x in values),
                 "invalid/partial route BF16 NaN and active arithmetic")
    expected_owners = {"gate_up", "down", "binding_refusals", "released_pinned", "released_cache", *faults}
    need(set(proof["owner_receipts"]) == expected_owners, "all nine actual Host owner teardowns")
    for name, receipt in proof["owner_receipts"].items():
        need(receipt["safe_to_exit"] is True and receipt["in_flight"] == receipt["live_bytes"] == 0,
             "indirect proof retained owner")
        need(receipt["exit_code"] == int(name in faults), "expected versus clean owner outcome")
        if name in faults:
            need(receipt["status"] == "failed-drained" and
                 proof["errors"][name] == "p211 indirect payload outside retained owned span",
                 "original pointer fault and drained failed owner")
    for prefix in ("gate", "down"):
        need(proof["byte_sha256"][prefix + "_cache_mutated"] != proof["byte_sha256"][prefix + "_reference"],
             "cache payload must affect arithmetic")


def indirect_proof(spec, env):
    directory = Path(spec["output"]) / "indirect-proof"
    argv = [spec["binary"], "--p211-indirect-proof", str(directory)]
    outcome = dict(passed=False, argv=argv, incident_sigterm_sent=False, retained_owner=False)
    with (Path(spec["output"]) / "indirect-proof.stdout.log").open("wb") as out, \
         (Path(spec["output"]) / "indirect-proof.stderr.log").open("wb") as err:
        process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired as primary:
            if not incident(process, outcome):
                save_result(Path(spec["output"]) / "indirect-proof-result.json", outcome, primary)
                hold_retained(process, Path(spec["output"]), primary)
            save_result(Path(spec["output"]) / "indirect-proof-result.json", outcome, primary)
            raise
    outcome["returncode"] = process.returncode
    save_result(Path(spec["output"]) / "indirect-proof-result.json", outcome)
    need(process.returncode == 0, "standalone indirect arithmetic proof process failed")
    proof_path = directory / "indirect-proof.json"
    proof = read(proof_path)
    validate_indirect_proof(proof)
    outcome.update(passed=True, proof=proof, proof_sha256=sha(proof_path))
    write(Path(spec["output"]) / "indirect-proof-result.json", outcome)
    return outcome


def failure_owner(spec, env):
    directory = Path(spec["output"]) / "intentional-partial-failure"
    directory.mkdir()
    (directory / "tokenizer.tsv").write_bytes(Path(spec["parent_reference"]["tokenizer"]).read_bytes())
    argv = owner_argv(spec["binary"], directory, "paired")
    argv[argv.index("--request-front-max-requests") + 1] = "2"
    argv.append("--p211-host-fail-after-row0")
    result = dict(passed=False, argv=argv, requested_runs=1, requested_controls=0,
                  retry=False, incident_sigterm_sent=False, retained_owner=False)
    process = None
    primary = None
    with (directory / "stderr.log").open("wb") as log:
        try:
            process = subprocess.Popen(argv, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
            front = client_class()(process, context=64, vocab=16, max_requests=2,
                                   startup_timeout=30, request_timeout=30)
            result["ready"] = front.ready
            error = None
            try:
                front.request("fault", [2, 5, 3, 7, 1], 2)
            except RuntimeError as caught:
                error = str(caught)
            need(error is not None and "p211 intentional partial chunk refusal" in error,
                 "partial chunk original failure not preserved")
            need(front.state == "halted", "failure channel did not halt")
            process.wait(timeout=60)
            need(process.returncode == 1, "intentional failure owner must exit1")
            owner = read(directory / "owner/receipt.json")
            need(owner["passed"] is False and owner["safe_to_exit"] is True and
                 owner["device_executed"] is False, "failed owner safe drain")
            need(not list((directory / "checkpoints").glob("*/manifest.json")), "failed chunk saved checkpoint")
            need(not (directory / "owner/requests/fault/result.json").exists(), "failed request emitted result")
            need(not jsonl(directory / "owner/requests/fault/prefill-chunks.jsonl"), "partial chunk emitted success trace")
            cache = read(directory / "owner/cache-failure.json")
            need(cache["cache_active"] is True and cache["poisoned"] is True and
                 cache["updating"] is False and cache["start"] == 0 and cache["count"] == 2 and
                 cache["rollback_claimed"] is False, "failed active cache interval was not poisoned")
            need(not jsonl(directory / "owner/requests/fault/cache-intervals.jsonl"),
                 "failed cache interval emitted successful maintenance")
            # Calling a halted transport must refuse locally; no second RUN is sent.
            refused = None
            try:
                front.request("must-not-run", [2, 5], 1)
            except RuntimeError as caught:
                refused = str(caught)
            need(refused is not None and not (directory / "owner/requests/must-not-run").exists(),
                 "poisoned request intake accepted another RUN")
            result.update(passed=True, cache_failure=cache, poisoned_intake_refusal=refused, original_error=error, owner=owner, returncode=process.returncode,
                          request_complete=False, checkpoint_saved=False, successful_chunk_published=False)
        except BaseException as error:
            primary = error
            result["error"] = dict(type=type(error).__name__, message=str(error))
            if process is not None:
                try:
                    exited = incident(process, result)
                except BaseException as cleanup:
                    exited = False
                    result["cleanup_error"] = repr(cleanup)
                if not exited:
                    save_result(directory / "result.json", result, primary)
                    hold_retained(process, directory, error)
        finally:
            save_result(directory / "result.json", result, primary)
            close_exited_pipes(process, primary)
        if primary is not None:
            raise primary
    return result


def execute(spec):
    limits()
    need(plan(Path(spec["output"])) == spec, "plan changed before execution")
    need(shutil.disk_usage(ROOT).free >= FLOOR + WRITE_BOUND, "root floor after write forecast")
    output = Path(spec["output"])
    output.mkdir()
    write(output / "plan.json", spec)
    result = dict(schema="packet211.host-proof.v1", passed=False, device_executed=False,
                  model_executed=False, native_host_executed=False, plan=spec)
    try:
        env = environment()
        result["parser_refusals"] = early_refusals(spec, env)
        result["indirect_arithmetic"] = indirect_proof(spec, env)
        result["native_host_executed"] = True
        write(output / "result.json", result)
        for name in ("direct", "serial", "paired"):
            result[name] = run_variant(spec, name, env)
            write(output / "result.json", result)
        result["correctness"] = compare(spec, result["direct"], result["serial"], result["paired"])
        result["intentional_partial_failure"] = failure_owner(spec, env)
        for name, digest in spec["source_sha256"].items():
            need(sha(ROOT / name) == digest, "harness source changed during run")
        need(sha(spec["binary"]) == spec["binary_sha256"], "binary changed during run")
        result["passed"] = True
    except BaseException as error:
        result["error"] = dict(type=type(error).__name__, message=str(error))
        save_result(output / "result.json", result, error)
        raise
    write(output / "result.json", result)
    target = P / "evidence/host-proof.json"
    need(not target.exists(), "preserve prior proof receipt")
    write(target, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run-host-only", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    need(args.plan != args.run_host_only, "select exactly one of --plan or --run-host-only")
    spec = plan(args.output)
    if args.plan:
        print(json.dumps(spec, indent=2, sort_keys=True))
    else:
        result = execute(spec)
        print(json.dumps(dict(passed=result["passed"], comparison_owners=3, failure_owners=1,
                              standalone_abi_processes=1, completed_requests=48,
                              paired_projection_sites=result["correctness"]["paired_projection_sites"],
                              intentional_failed_requests=1, device_executed=False)))


if __name__ == "__main__":
    main()
