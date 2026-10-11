#!/usr/bin/env python3
"""CPU-only Markdown summaries of reference-runtime screening receipts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def successful(row):
    return bool(row) and row.get("returncode") == 0 and row.get("failed") is False


def rate(row, kind):
    if not successful(row):
        return None
    timing = row.get("timings", {}).get(kind)
    if not timing:
        return None
    value = timing.get("reported_tokens_per_second")
    if (not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
            or timing.get("milliseconds", 0) <= 0 or timing.get("count", 0) <= 0):
        return None
    return value


def flag(row, name):
    argv = row.get("argv", [])
    try:
        return argv[argv.index(name) + 1]
    except (ValueError, IndexError):
        return None


def generated_tokens(row, output):
    """Non-EOG generated tokens for this pinned noninteractive completion plan.

    At 23b0202a, completion.cpp:667-683 samples before the next decode,
    :928-930 stops on EOG; llama-context.cpp:3561 clamps n_eval to at least 1.
    Thus 63 decode runs at a 64-token cap means 64 output tokens; early EOG
    leaves n_eval non-EOG tokens (the final EOG is not evaluated). Zero-time
    decode means no decode steps, not one generated text token. Do not call
    the perf eval count the generated-token count or tokenize output bytes.
    """
    if not successful(row):
        return None
    timing = row.get("timings", {})
    decode = timing.get("decode")
    if decode is None:
        return 0 if timing.get("generated_tokens") == 0 else None
    if rate(row, "decode") is None:
        return None
    count = decode.get("count")
    if not isinstance(count, int) or decode.get("count_unit") != "runs":
        return None
    if output is not None and output.endswith(b" [end of text]\n\n\n"):
        return count
    cap = flag(row, "--predict")
    if cap is not None and cap.isdigit() and count + 1 == int(cap):
        return count + 1
    return None


def median(values):
    values = [v for v in values if v is not None]
    return {"value": statistics.median(values) if values else None, "n": len(values)}


def summarise(directory, prompt_ids=None):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"not a run directory: {directory}")
    rows = read_json(directory / "runs.json", [])
    if not isinstance(rows, list):
        raise ValueError(f"runs.json must contain a list: {directory}")
    if prompt_ids is None:
        prompt_ids = [p["id"] for p in read_json(HERE / "prompt-receipt.json")["prompts"]]
    indexed = {}
    for row in rows:
        key = (row["id"], row["repeat"])
        if key in indexed or key[0] not in prompt_ids or key[1] not in (1, 2):
            raise ValueError(f"duplicate or unregistered row: {key}")
        indexed[key] = row
    environment = read_json(directory / "environment.json", {})
    deltas = read_json(directory / "run-identity-deltas.json", {})
    fault = (directory / "FAULT.json").exists()
    table = []
    for prompt in prompt_ids:
        repeats = []
        outputs = []
        for repeat in (1, 2):
            row = indexed.get((prompt, repeat), {})
            path = directory / f"repeat{repeat}-{prompt}.stdout"
            output = path.read_bytes() if path.is_file() else None
            verified = (output is not None and bool(output.strip()) and
                        hashlib.sha256(output).hexdigest() == row.get("stdout_sha256"))
            status = "missing" if not row else "ok" if successful(row) else "failed"
            if row and successful(row) and not verified:
                status = "stdout missing/unverified"
            repeats.append({"decode": rate(row, "decode"), "prefill": rate(row, "prefill"),
                            "generated_tokens": generated_tokens(row, output if verified else None),
                            "status": status})
            outputs.append(output if successful(row) and verified else None)
        equality = None if any(o is None for o in outputs) else outputs[0] == outputs[1]
        table.append({"id": prompt, "repeats": repeats, "byte_equal": equality})
    comparison = read_json(directory / "comparison.json")
    all_rows = len(rows) == len(prompt_ids) * 2 and all(successful(r) for r in rows)
    complete = all_rows and comparison is not None and all(p["byte_equal"] is not None for p in table)
    status = "FAULT / partial" if fault else "complete" if complete else "partial"
    if complete and any(p["byte_equal"] is False for p in table):
        status += " / repeat mismatch"
    medians = {}
    for label, indices in (("repeat1", (0,)), ("repeat2", (1,)), ("all observed", (0, 1))):
        medians[label] = {kind: median([p["repeats"][i][kind] for p in table for i in indices])
                          for kind in ("decode", "prefill")}
    return {"directory": str(directory), "status": status, "rows": len(rows),
            "expected": len(prompt_ids) * 2, "table": table, "medians": medians,
            "device_selector": environment.get("ONEAPI_DEVICE_SELECTOR", "not recorded"),
            "device_lists": sorted({flag(r, "--device") or "not recorded" for r in rows}),
            "plan": deltas.get("plan", "not recorded"), "fault": fault}


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def number(value):
    return "—" if value is None else f"{value:.2f}"


def render(summaries):
    lines = ["# Reference-runtime baseline screen", "",
             "Unmodified llama.cpp reference-runtime baseline, not our runtime; not certified. "
             "These are 64-token screening runs, not the realistic final gate or a lossless CPU-oracle pass.", "",
             "Decode and prompt rates are runtime-reported tokens/s. Prompt rates use each prompt’s actual "
             "input length, not a measured 512-token prefill benchmark. Generated tokens exclude EOG: "
             "the pinned completion loop generates 64 tokens with 63 timed decode runs at the cap; "
             "immediate EOG is 0. Early EOG counts use the retained stdout end marker. Unknown counts are —.", "",
             "Byte-equal compares hash-verified retained stdout from two successful processes, including "
             "the CLI end marker; it does not establish token-oracle parity or useful output. Missing, "
             "failed, empty or unverified output is unassessed. Medians exclude failed/missing/nonfinite/zero "
             "rates and retain immediate-EOG prompt rates. Runs from different directories are never pooled.", ""]
    for summary in summaries:
        lines += [f"## {cell(summary['directory'])}", "",
                  f"Status: **{summary['status']}**; {summary['rows']}/{summary['expected']} rows recorded. "
                  "Medians below describe observed rows only, including pre-fault rows if the window faulted.", "",
                  f"ONEAPI_DEVICE_SELECTOR: `{cell(summary['device_selector'])}`; llama --device: "
                  f"`{cell(', '.join(summary['device_lists']))}`; plan: `{cell(summary['plan'])}`.", "",
                  "| Prompt | R1 decode tok/s | R2 decode tok/s | R1 prompt tok/s | R2 prompt tok/s | R1 generated | R2 generated | Byte-equal | R1 / R2 status |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
        for p in summary["table"]:
            a, b = p["repeats"]
            eq = "unassessed" if p["byte_equal"] is None else "yes" if p["byte_equal"] else "NO"
            generated = ["—" if r["generated_tokens"] is None else str(r["generated_tokens"]) for r in (a, b)]
            values = [p["id"], number(a["decode"]), number(b["decode"]), number(a["prefill"]),
                      number(b["prefill"]), *generated, eq, f"{a['status']} / {b['status']}"]
            lines.append("| " + " | ".join(cell(v) for v in values) + " |")
        lines += ["", "| Observed-row median | Decode tok/s (n) | Prompt tok/s (n) |",
                  "| --- | ---: | ---: |"]
        for label, metrics in summary["medians"].items():
            values = [f"{number(metrics[k]['value'])} ({metrics[k]['n']})" for k in ("decode", "prefill")]
            lines.append(f"| {label} | {' | '.join(values)} |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, help="Markdown output; defaults to stdout")
    args = parser.parse_args()
    try:
        output = render([summarise(path) for path in args.run_dirs]).rstrip()
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    if args.out:
        args.out.write_text(output + "\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
