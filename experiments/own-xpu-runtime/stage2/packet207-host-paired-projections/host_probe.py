#!/usr/bin/env python3
"""Two same-binary comparison owners; synthetic HOST_ONLY paired projections only."""
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
P206 = P.parent / "packet206-host-engine-chunk"
PYTHON = Path("/home/steve/.venvs/vllm-xpu/bin/python")
OUTPUT = P / "build/host-proof-a"
FLOOR = 27_000_000_000
WRITE_BOUND = 64 * 1024**2
LABEL = "experimental-host-paired-projections"
CONTRACT = "v1.2+p207"
EARLY_REFUSAL = "p207 chunk2 requires HOST_ONLY mini pipeline resident single-owner mode"


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
    spec = importlib.util.spec_from_file_location("p207_pinned_front", path)
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


def owner_argv(binary, run, chunk):
    argv = [str(binary), "--mini", "--pipeline-mini", "--memory", "resident",
            "--context", "64", "--retain-steps", "none", "--native-nice", "19",
            "--seconds", "180", "--request-front", "--request-front-max-requests", "16",
            "--request-front-idle-seconds", "15", "--request-front-checkpoints", str(run / "checkpoints"),
            "--request-front-tokenizer-identity", str(run / "tokenizer.tsv"), "--output", str(run / "owner")]
    if chunk:
        argv.append("--p207-host-chunk2")
    argv.append("--p207-host-observe")
    return argv


def p206_reference():
    """External immutable bytes only; never restore its different binary identity."""
    proof_path = P206 / "evidence/host-proof.json"
    proof = read(proof_path)
    inventory_path = P206 / "evidence/raw-host-proof-index.json"
    inventory = read(inventory_path)
    need(proof["passed"] and not proof["device_executed"] and not proof["model_executed"],
         "P206 successful tiny host authority")
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
             "P206 external checkpoint changed: " + str(relative))
    return dict(receipt=str(proof_path), receipt_sha256=sha(proof_path), directory=str(directory),
                inventory_sha256=sha(inventory_path),
                files_sha256={str(directory / path): sha(directory / path) for path in paths})


def plan(output=OUTPUT):
    output = Path(output)
    need(output.parent == P / "build" and output.name.startswith("host-proof-"), "fixed packet scratch namespace")
    need(not os.path.lexists(output), "preserve existing output; no automatic retry")
    need(not (P / "evidence/host-proof.json").exists(), "preserve prior proof receipt")
    host = binary_plan()
    fixtures = read(P / "fixtures.json")
    need(len(fixtures["rows"]) == 16 and fixtures["context"] == 64, "fixed fixture count/context")
    paths = [Path(__file__), P / "fixtures.json", P / "authority-inputs.json",
             ROOT / "experiments/own-xpu-runtime/integration/request_front/client_v2.py",
             P.parent / "packet181-session-swap-v3/one-card/native_env.py",
             P.parent / "packet181-session-swap-v3/one-card/common.py"]
    return dict(schema="packet207.host-proof-plan.v1", passed=True, executed=False,
                output=str(output), binary=host["binary"], binary_sha256=host["binary_sha256"],
                build_receipt_sha256=sha(P / "evidence/build-compile-only.json"),
                source_sha256={str(x.relative_to(ROOT)): sha(x) for x in paths},
                parent_reference=parent_reference(), p206_reference=p206_reference(),
                comparison_owners=2, failure_owners=0,
                total_owner_processes=2, requests_per_comparison_owner=16,
                standalone_abi_processes=1, parser_refusal_processes=10,
                abi_argv=[host["binary"], "--p207-pair-proof", str(output / "pair-proof")],
                saves_per_owner=13, releases_per_owner=3, context=64, vocab=16,
                disk_floor_bytes=FLOOR, planned_write_bytes=WRITE_BOUND,
                argv={name: owner_argv(host["binary"], output / name, name == "chunk")
                      for name in ("serial", "chunk")},
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


def traces(directory, tokens, start, resumed, chunk, cap, state_names):
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
    need([row["token_index"] for row in singles] == remaining, "single-row prefill coverage")
    observed = jsonl(directory / "serial-prefill-state.jsonl")
    need([row["start"] for row in observed] == remaining, "serial endpoint state coverage")
    for row in observed:
        need(row["count"] == 1 and row["published_position"] == row["start"] + 1 and
             set(row["canonical_state_sha256"]) == state_names, "serial endpoint state schema")
    return dict(chunks=rows, serial_endpoints=observed,
                generated_indices=wanted, single_prefill_positions=remaining)


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
                               name == "chunk", row["max_new"], state_names)
                pairs = paired_sites(directory, row["id"], trace, name == "chunk")
                need(native["p207_host_chunk2"] is (name == "chunk") and
                     native["p207_chunk_count"] == len(trace["chunks"]), "native chunk reporting")
                record = dict(id=row["id"], input=tokens, tokens=generated, start_position=start,
                              same_generation=resumed, control=event, trace=trace, paired_sites=pairs)
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
            if name == "chunk":
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
    expected = [(chunk["start"], layer, op) for chunk in trace["chunks"]
                for layer in (0, 2) for op in ("qkv", "z")]
    need([(row["start"], row["layer"], row["op"]) for row in records] == expected,
         "actual paired projection schedule differs")
    if not candidate:
        need(not records, "serial owner issued paired projection")
        return records
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
        inputs = [allocation(f"p207:row{r}:retained0", 32) for r in range(2)]
        outputs = [allocation(f"p207:row{r}:retained{output_slot}", output_bytes) for r in range(2)]
        inject = [allocation(f"p207:row{r}:retained1", 8) for r in range(2)]
        workspace = [allocation(f"p207:pair-workspace{r}", 4) for r in range(2)]
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
    base = [spec["binary"], "--p207-host-chunk2", "--mini", "--pipeline-mini", "--memory", "resident",
            "--context", "64", "--retain-steps", "none"]
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


def arithmetic_proof(spec, env):
    """One bounded synthetic ABI process, separate from the two Engine owners."""
    folder = Path(spec["output"]) / "abi-proof-driver"
    folder.mkdir()
    result = dict(passed=False, argv=spec["abi_argv"], incident_sigterm_sent=False,
                  retained_owner=False, model_executed=False, device_executed=False)
    process = None
    primary = None
    with (folder / "stdout.log").open("wb") as out, (folder / "stderr.log").open("wb") as err:
        try:
            process = subprocess.Popen(spec["abi_argv"], env=env, stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=err)
            process.wait(timeout=120)
            need(process.returncode == 0, "synthetic paired ABI process failed")
            path = Path(spec["output"]) / "pair-proof/pair-proof.json"
            need(path.stat().st_size < 256 * 1024, "bounded ABI receipt")
            proof = read(path)
            need(proof["passed"] and not proof["device_executed"] and not proof["model_executed"]
                 and not proof["error"], "paired ABI proof scope/status")
            need([row["rows"] for row in proof["cases"]] == [10240, 6144], "full qkv/z output shapes required")
            for row in proof["cases"]:
                need(row["passed"] and row["columns"] == 2560 and row["variant"] == 6 and
                     row["stride"] == 3380 and row["captured_operations"] == 1, "paired Q6 ABI identity")
                need(len(row["outputs"]) == 2 and row["outputs"][0]["sha256"] != row["outputs"][1]["sha256"],
                     "distinct paired rows must discriminate")
                for item in row["outputs"]:
                    need(item["bytes"] == row["rows"] * 2 and item["p33_equal"] and
                         len(item["sha256"]) == 64 and all(c in "0123456789abcdef" for c in item["sha256"]),
                         "independent p33 exact BF16 reference")
                for check in ("changed_row_independent", "changed_weight_consumed", "caller_metadata_immutable",
                              "alias_extent_layout_refusals_unchanged"):
                    need(row[check] is True, "paired ABI mutation/refusal gate: " + check)
            need(len(proof["teardown"]) == 2, "both standalone synthetic Devices must close")
            for teardown in proof["teardown"]:
                need(teardown["safe_to_exit"] and teardown["exit_code"] == 0 and
                     teardown["in_flight"] == teardown["live_bytes"] == 0, "ABI safe drained shutdown")
            result.update(passed=True, returncode=process.returncode, proof=proof,
                          proof_sha256=sha(path), stdout_sha256=sha(folder / "stdout.log"),
                          stderr_sha256=sha(folder / "stderr.log"))
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
                    save_result(folder / "result.json", result, primary)
                    hold_retained(process, folder, primary)
        finally:
            save_result(folder / "result.json", result, primary)
        if primary is not None:
            raise primary
    return result


def compare_states(left, right):
    need(left["files_sha256"] == right["files_sha256"] and left["sizes"] == right["sizes"], "checkpoint bytes differ")
    need(left["token_state"] == right["token_state"], "checkpoint token/control descriptor differs")


def compare(spec, serial, chunk):
    need([x["id"] for x in serial["rows"]] == [x["id"] for x in chunk["rows"]], "request order")
    compared_endpoints = 0
    for left, right in zip(serial["rows"], chunk["rows"]):
        need(left["input"] == right["input"] and left["tokens"] == right["tokens"], "serial/chunk tokens")
        need(left["trace"]["generated_indices"] == right["trace"]["generated_indices"], "decode path indices")
        serial_endpoints = {row["published_position"]: row["canonical_state_sha256"]
                            for row in left["trace"]["serial_endpoints"]}
        for row in right["trace"]["chunks"] + right["trace"]["serial_endpoints"]:
            need(serial_endpoints[row["published_position"]] == row["canonical_state_sha256"],
                 "intermediate canonical state differs: " + right["id"] + ":" + str(row["published_position"]))
            compared_endpoints += 1
    paired_count = sum(len(row["paired_sites"]) for row in chunk["rows"])
    skipped_count = sum(site["skipped_original_sites"] for row in chunk["rows"] for site in row["paired_sites"])
    need(paired_count == 400 and skipped_count == 800, "paired execution must replace original projection sites")
    need(compared_endpoints == 108, "complete frozen prefill endpoint coverage")
    need(serial["checkpoints"].keys() == chunk["checkpoints"].keys(), "checkpoint inventory")
    for checkpoint_id in serial["checkpoints"]:
        compare_states(serial["checkpoints"][checkpoint_id], chunk["checkpoints"][checkpoint_id])
    prior = read(spec["parent_reference"]["receipt"])["lifecycle"]
    p206 = read(spec["p206_reference"]["receipt"])["serial"]
    for name in ("serial", "chunk"):
        result = serial if name == "serial" else chunk
        for row, old in zip(result["rows"], p206["rows"], strict=True):
            need(row["id"] == old["id"] and row["input"] == old["input"] and
                 row["tokens"] == old["tokens"], "P206 recorded inputs/outputs differ")
        for checkpoint_id in result["checkpoints"]:
            old = checkpoint(Path(spec["p206_reference"]["directory"]) / "serial/checkpoints" / checkpoint_id)
            compare_states(result["checkpoints"][checkpoint_id], old)
        for row, old in zip(result["rows"][:8], prior["requests"]):
            need(row["id"] == old["id"] and row["tokens"] == old["tokens"], "parent recorded output")
        for checkpoint_id in ("s1", "s2", "s3", "s4", "s5", "s6"):
            old = checkpoint(Path(spec["parent_reference"]["directory"]) / "checkpoints" / checkpoint_id)
            compare_states(result["checkpoints"][checkpoint_id], old)
        for a, b in (("s3", "s4"), ("s3", "s5"), ("boundary-append", "boundary-fresh")):
            compare_states(result["checkpoints"][a], result["checkpoints"][b])
        need(result["checkpoints"]["boundary-seed"]["token_state"]["position"] == 31, "pending boundary position")
        rows = {row["id"]: row for row in result["rows"]}
        need(rows["boundary-append"]["input"][31] == result["checkpoints"]["boundary-seed"]["token_state"]["next_token"],
             "append starts with saved pending token")
        need(rows["fresh-a"]["tokens"] + rows["resume-a"]["tokens"] == rows["fresh-a-reference"]["tokens"], "resume/uninterrupted tokens")
        need(rows["fresh-b"]["tokens"] == rows["final-b-release"]["tokens"], "B reset repeat")
    return dict(all13_same_binary_checkpoints_exact=True, all20_blobs_plus_tokens_exact=True,
                all13_p206_external_checkpoints_exact=True, all16_p206_inputs_outputs_exact=True,
                paired_projection_sites=paired_count, original_projection_sites_skipped=skipped_count,
                six_parent_checkpoints_exact=True, all16_generated_sequences_exact=True,
                append_pending_31_to_32_exact=True, final_prompt_decode_resume_serial=True,
                intermediate_endpoints_exact=compared_endpoints)


def execute(spec):
    limits()
    need(plan(Path(spec["output"])) == spec, "plan changed before execution")
    need(shutil.disk_usage(ROOT).free >= FLOOR + WRITE_BOUND, "root floor after write forecast")
    output = Path(spec["output"])
    output.mkdir()
    write(output / "plan.json", spec)
    result = dict(schema="packet207.host-proof.v1", passed=False, device_executed=False,
                  model_executed=False, native_host_executed=False, plan=spec)
    try:
        env = environment()
        result["parser_refusals"] = early_refusals(spec, env)
        result["native_host_executed"] = True
        result["paired_abi"] = arithmetic_proof(spec, env)
        write(output / "result.json", result)
        serial = run_variant(spec, "serial", env)
        result["serial"] = serial
        write(output / "result.json", result)
        chunk = run_variant(spec, "chunk", env)
        result["chunk"] = chunk
        result["correctness"] = compare(spec, serial, chunk)
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
        print(json.dumps(dict(passed=result["passed"], comparison_owners=2, failure_owners=0,
                              standalone_abi_processes=1, completed_requests=32,
                              paired_projection_sites=result["correctness"]["paired_projection_sites"],
                              intentional_failed_requests=0, device_executed=False)))


if __name__ == "__main__":
    main()
