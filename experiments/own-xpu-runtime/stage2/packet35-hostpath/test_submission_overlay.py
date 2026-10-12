"""CPU-only regression gate for the generated host submission adaptation."""
import hashlib
import json
import re
from pathlib import Path
from kernel_overlay import apply
from submission_overlay import apply_submission_overlay, _closing
from math_gate import closure, ROOT

HERE = Path(__file__).resolve().parent


def kernels(text):
    out = []
    for match in re.finditer(r"\.\s*(parallel_for|single_task)(?:<[^;]*?>)?\s*\(", text):
        kernel = re.search(r"\[=\]\s*(?:\([^;]*?\))?\s*(?:\[\[.*?\]\])?\s*\{", text[match.end():], re.S)
        if not kernel:
            continue
        start = match.end()+kernel.start()
        body = match.end()+kernel.end()-1
        end = _closing(text, body, "{", "}")
        out.append(text[start:end])
    return out


def run():
    rows = []
    for source in closure():
        before = apply(source, source.read_text())
        after = apply_submission_overlay(source, before)
        if before == after:
            continue
        assert after.startswith('#ifndef OWN_RT_HOST_ONLY\n#include "prepared_submission.hpp"\n#endif\n#line 1\n')
        original, prepared = kernels(before), kernels(after)
        assert original == prepared, (source, "device lambda differs")
        for call in re.finditer(r"ownrt::prepared_submit\(q,", after):
            begin = after.index("{", call.end())
            end = _closing(after, begin, "{", "}")
            body = re.sub(r"//[^\n]*|/\*.*?\*/", "", after[begin:end], flags=re.S)
            for transient in ("p", "deps", "this", "reference_wrapper"):
                assert not re.search(r"\b"+transient+r"\b", body), (source, transient)
        count = len(re.findall(r"\bq\.submit\(", before))
        assert count == after.count("ownrt::prepared_submit(q,"), source
        assert not re.search(r"\bq\.submit\(", after), source
        assert not re.search(r"\b\w+\.depends_on\(deps\)", after), source
        rows.append(dict(source=str(source.relative_to(ROOT)), submissions=count,
                         kernel_count=len(original),
                         kernel_source_sha256=[hashlib.sha256(k.encode()).hexdigest() for k in original],
                         range_captures=len(re.findall(r"p35_range\d+=", after))))
    assert sum(r["submissions"] for r in rows) == 28
    assert sum(r["range_captures"] for r in rows) == 26
    # Guard the fail-closed parser: unsupported range syntax must not fall back.
    try:
        apply_submission_overlay(Path("negative"), "return q.submit([&](sycl::handler& h){h.parallel_for(dynamic_range,[=](sycl::id<1> i){});});")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported range admitted")
    helper = (HERE/"prepared_submission.hpp").read_text()
    backend = (HERE/"backend.hpp").read_text()
    assert "virtual sycl::event issue" not in helper
    assert "bound->issue()" not in backend
    assert "return captured->make_callback({&events,&mutex,&error,&allocation_card,card});" in backend
    callback = helper.split("return [queue=queue,command=command,state]", 1)[1].split("\n    };", 1)[0]
    assert "queue->submit(command)" in callback
    for forbidden in ("make_callback", "make_unique", "make_shared", "get_device", "get_info", "chrono", "map<", "malloc"):
        assert forbidden not in callback, forbidden
    payload=dict(passed=True, device_run=False, submission_count=28,
                 range_count=26, source_files=len(rows), sources=rows,
                 checks=["device lambda source bytes unchanged", "every operation intercepted",
                         "predecessor dependencies omitted", "ranges captured once",
                         "unknown range syntax rejected", "no transient binding-span captures", "single direct-submit callback", "source line identity restored"])
    (HERE/"submission-overlay-gates.json").write_text(json.dumps(payload, indent=2)+"\n")
    print(json.dumps({k:v for k,v in payload.items() if k!="sources"}))

if __name__ == "__main__":
    run()
