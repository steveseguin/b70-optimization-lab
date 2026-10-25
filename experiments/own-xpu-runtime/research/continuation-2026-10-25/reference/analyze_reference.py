#!/usr/bin/env python3
"""Bounded CPU audit of retained rows and approximately 3.2 MiB sealed tensors."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
OWNRT = HERE.parents[2]
REFERENCE = OWNRT / "gsq-rco-iq3s/service-speed/e-reference"


def identity(path):
    data = Path(path).read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def analyze_rows(inp, rows):
    tokens, start = inp["tokens"], inp["score_from"]
    if not 1 <= start < len(tokens):
        raise ValueError("invalid score_from")
    if [r["position"] for r in rows] != list(range(start-1, len(tokens))):
        raise ValueError("missing, duplicate, or reordered reference position")
    disagreements = []
    for row in rows:
        p = row["position"]
        top = row["top"]
        if not top or top[0][0] != row["argmax"]:
            raise ValueError("argmax/top inconsistency")
        if p == len(tokens)-1:
            if "next" in row:
                raise ValueError("terminal row cannot score a nonexistent token")
            continue
        if row.get("next") != tokens[p+1]:
            raise ValueError("teacher-forced next token differs from retained input")
        if row["argmax"] != row["next"]:
            rank = next((i+1 for i,t in enumerate(top) if t[0] == row["next"]), None)
            disagreements.append({"position": p, "output_index": p+1-start,
                "reference_argmax": row["argmax"], "engine_token": row["next"],
                "engine_token_reference_rank": rank,
                "reference_top_logit": top[0][1], "engine_token_reference_logit": row["next_logit"],
                "reference_margin": top[0][1]-row["next_logit"]})
    return {"prompt_tokens": start, "scored_positions": len(tokens)-start,
            "disagreements": disagreements, "terminal_unscored_rows": 1}


def compare_rows(base, diagnostic):
    if [r["position"] for r in base] != [r["position"] for r in diagnostic]:
        raise ValueError("diagnostic positions differ")
    deltas = []
    for a,b in zip(base,diagnostic):
        if a.get("next") != b.get("next"):
            raise ValueError("diagnostic teacher-forced token differs")
        aa,bb = {r[0]: r[1] for r in a["top"]}, {r[0]: r[1] for r in b["top"]}
        deltas.extend(abs(aa[t]-bb[t]) for t in aa.keys() & bb.keys())
    return {"argmax_changes": sum(a["argmax"] != b["argmax"] for a,b in zip(base,diagnostic)),
            "max_abs_emitted_token_logit_delta": max(abs(a["next_logit"]-b["next_logit"]) for a,b in zip(base,diagnostic) if "next" in a),
            "max_abs_common_top20_logit_delta": max(deltas),
            "scope": "serialized next-token and common top20 logits; not full-vocabulary maximum"}


def capture_layout(key_heads=16, value_heads=48, width=128, lanes=32):
    """Prove unique lane ownership and exact bounds for an actual-Q store."""
    if min(key_heads,value_heads,width,lanes)<=0 or value_heads%key_heads or width%lanes:
        raise ValueError("unsupported diagnostic capture dimensions")
    writes=[]
    for h in range(value_heads):
        for row in range(width):
            if row!=0 or h>=key_heads:
                continue
            for lane in range(lanes):
                for z in range(width//lanes):
                    writes.append(h*width+lane*(width//lanes)+z)
    if sorted(writes)!=list(range(key_heads*width)):
        raise ValueError("capture writes overlap or leave holes")
    return {"packed_heads":True,"key_heads":key_heads,"value_heads":value_heads,
            "width":width,"subgroup_lanes":lanes,"float_values":len(writes),
            "bytes":len(writes)*4,"max_byte_offset":(max(writes)+1)*4-1,
            "each_element_written_once":True,"writer_predicate":"j == 0 && h < key_heads"}


def sealed_embedding(dump, dest, name="embedding.bin", expected_size=10240):
    index = dump / "state-index.tsv"
    lines = index.read_text().splitlines()
    if lines[0] != "GSQ_STATE_BUNDLE_V1":
        raise ValueError("unrecognized bundle")
    entries = [line.split("\t") for line in lines[1:]]
    matches = [r for r in entries if r[0] == name]
    if len(matches) != 1 or int(matches[0][2]) != expected_size:
        raise ValueError("missing or wrong-size embedding")
    name, offset, size, expected = matches[0]
    with (dump / "state.bundle").open("rb") as source:
        source.seek(int(offset)); data = source.read(int(size))
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("embedding hash differs from sealed index")
    dest.write_bytes(data)
    return {"bundle_path": str(dump / "state.bundle"), "index": identity(index),
            "name": name, "offset": int(offset), "bytes_read": len(data),
            "sha256": expected, "scope": "PP2 pos118 saved tensor, not a discrepant suite position"}


def operator_probe(llref, fixture):
    source = HERE / "operator_probe.cpp"
    libs = [llref / "build/ggml/src" / n for n in ("libggml-cpu.a", "libggml-base.a")]
    with tempfile.TemporaryDirectory(prefix="sc117-operators-") as temp:
        binary = Path(temp)/"probe"
        command = ["g++-13", "-std=c++20", "-O2", "-ffp-contract=off", "-march=native",
                   "-I"+str(OWNRT/"engine/src"), "-I"+str(llref/"ggml/src/ggml-cpu"),
                   "-I"+str(llref/"ggml/include"), "-I"+str(llref/"ggml/src"),
                   str(source), *map(str,libs), "-fopenmp", "-o", str(binary)]
        subprocess.run(command, check=True, capture_output=True)
        output = json.loads(subprocess.check_output([str(binary), str(fixture), str(HERE/"frozen-gdn-conv.f32"),
                           str(HERE/"frozen-gdn-state.f32"),str(HERE/"frozen-gdn-y.f32")]))
        output["binary"] = identity(binary)
    output["build_command"] = command
    files = libs + [source, llref/"ggml/src/ggml-cpu/vec.h", llref/"ggml/src/ggml-cpu/vec.cpp",
                    llref/"ggml/src/ggml-cpu/ops.cpp",llref/"ggml/src/ggml-cpu/ggml-cpu.c",
                    llref/"src/models/qwen4exp.cpp", llref/"build/compile_commands.json",
                    llref/"src/models/models.h",
                    OWNRT/"engine/src/stage2/packet194-expert-diet-engine/specialised.hpp",
                    OWNRT/"engine/src/stage2/packet194-expert-diet-engine/round2_submit.cpp",
                    OWNRT/"engine/src/stage2/packet17-detmath/detmath.hpp"]
    output["source_and_library_identities"] = [identity(p) for p in files]
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llref",type=Path,default=Path("/dev/shm/llref"))
    parser.add_argument("--dump",type=Path,default=Path("/dev/shm/sc117-pipeline-review-20261025/pp2-v2/stage0/native/state-2147483647"))
    parser.add_argument("--out",type=Path,default=HERE/"summary.json")
    args=parser.parse_args()
    suite=REFERENCE/"runs/f32suite"
    output={"schema":"ownrt.cpu-reference-audit.v1", "scope":"teacher-forced agreement, not independent free-running output identity", "prompts":[],"diagnostics":[],"inputs":[]}
    output["audit_implementation"]=[identity(Path(__file__)),identity(HERE/"test_analyze_reference.py")]
    for path in sorted((suite/"inputs").glob("in-*.json")):
        name=path.stem[3:]; inp=json.loads(path.read_text()); rowpath=suite/(name+".rows.jsonl"); rows=read_rows(rowpath)
        output["inputs"] += [identity(path),identity(rowpath)]
        result=analyze_rows(inp,rows); result["id"]=name;output["prompts"].append(result)
        if result["disagreements"]:
            for mode,diag in [("f32lane",Path(f"/dev/shm/exactref/f32lane/out-{name}/rows.jsonl")),
                              ("rope-powf",Path(f"/dev/shm/exactref/rope/out-powf-{name}/rows.jsonl")),
                              ("rope-f64",Path(f"/dev/shm/exactref/rope/out-f64-{name}/rows.jsonl"))]:
                output["diagnostics"].append({"id":name,"mode":mode,"input":identity(diag),**compare_rows(rows,read_rows(diag))})
    count=sum(r["scored_positions"] for r in output["prompts"])
    bad=sum(len(r["disagreements"]) for r in output["prompts"])
    output["aggregate"]={"scored_positions":count,"disagreements":bad,"agreement_fraction":(count-bad)/count}
    fixture=HERE/"frozen-embedding.f32"
    output["fixture"]=sealed_embedding(args.dump,fixture)
    output["gdn_fixture"]=sealed_embedding(args.dump,HERE/"frozen-gdn-conv.f32","blk.0.gdn.conv.bin",40960)
    output["gdn_state_fixture"]=sealed_embedding(args.dump,HERE/"frozen-gdn-state.f32","blk.0.gdn.state.bin",48*128*128*4)
    output["gdn_y_fixture"]=sealed_embedding(args.dump,HERE/"frozen-gdn-y.f32","blk.0.gdn.y.bin",48*128*4)
    output["operator_probe"]=operator_probe(args.llref,fixture)
    techpath=suite/"inputs/in-technical-guide.json"
    tech=json.loads(techpath.read_text())
    first=next(r for r in output["prompts"] if r["id"]=="technical-guide")["disagreements"][0]
    capture={"schema":"ownrt.gdn-consumed-q-capture-request.v1", "scope":"diagnostic only, not a launch authorization",
             "input":identity(techpath),"layer":0,"absolute_input_position":first["position"],
             "output_index":first["output_index"],"original_prompt_tokens":tech["score_from"],
             "teacher_forced_native_prompt_tokens":tech["tokens"][:first["position"]+1],
             "expected_engine_next_token":first["engine_token"],"expected_cpu_next_token":first["reference_argmax"],
             "generate_tokens":1,"speculation_enabled":False,"layout":capture_layout(),
             "existing_dispatch":identity(OWNRT/"gsq-rco-iq3s/serving/lan/dispatch-f32-select-gdn2.json"),
             "kernel":"round2_submit.cpp:gdn_device", "required_capture":"existing q[z] after normalization and scaling, without recomputation",
             "qualification":"Capture off/on must preserve every canonical state byte and output; replay with consumed-Q must exactly reproduce stored GDN y."}
    (HERE/"capture-request.json").write_text(json.dumps(capture,indent=2,ensure_ascii=False)+"\n")
    args.out.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"output":str(args.out),**output["aggregate"]}))


if __name__ == "__main__":
    main()
