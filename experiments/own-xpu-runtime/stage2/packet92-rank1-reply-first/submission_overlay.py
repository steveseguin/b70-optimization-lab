"""Host submission adaptation; device lambda bodies and scopes stay intact."""
import re


def _closing(text, start, left="(", right=")"):
    depth = 1
    i = start + 1
    while depth:
        depth += (text[i] == left) - (text[i] == right)
        i += 1
    return i


def apply_submission_overlay(path, text):
    # The backend's copy/marker and one-card ownership retain their event path.
    pattern = r"\bq\.submit\(\[&\]\(sycl::handler\s*&\s*(\w+)\)"
    matches = list(re.finditer(pattern, text))
    if not matches:
        return text
    edits = []
    for m in matches:
        body_start = text.index("{", m.end())
        body_end = _closing(text, body_start, "{", "}")
        body = text[body_start:body_end]
        # A capture initializer evaluates the range once while preparing the
        # command group. The kernel lambda stays lexically inside the original
        # submit/run method and inside the same command-group lambda.
        captures = []
        # Imported packet7 Stream uses a host-only operation member in its CG.
        # Freeze the scalar itself; retaining the transient Operation is unsafe.
        if path.parent.name == "packet7-kopt2" and "if(copy)" in body:
            captures.append("copy=copy")
        for n, call in enumerate(re.finditer(r"\b"+m[1]+r"\.parallel_for\(", body)):
            arg_start = body_start + call.end()
            if not text.startswith(("sycl::range<", "sycl::nd_range<"), arg_start):
                raise ValueError((path, "unrecognised prepared kernel range"))
            paren = text.index("(", arg_start)
            arg_end = _closing(text, paren)
            expression = text[arg_start:arg_end]
            name = "p35_range"+str(n)
            captures.append(name+"="+expression)
            edits.append((arg_start, arg_end, name))
        replacement = "ownrt::prepared_submit(q,[="
        if captures:
            replacement += ","+",".join(captures)
        replacement += "](sycl::handler& "+m[1]+")"
        edits.append((m.start(), m.end(), replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start]+replacement+text[end:]
    # The in-order predecessor is already ordered. Device/Context keep the
    # independent card ownership and drained-transition checks.
    text = re.sub(r"\b(\w+)\.depends_on\(deps\);", "", text)
    return '#ifndef OWN_RT_HOST_ONLY\n#include "prepared_submission.hpp"\n#endif\n#line 1\n'+text
