"""Read-only validation of P45's owned-argument mirror and P46 include binding.

The transform below follows P45 kernel_gate.py. It never writes its input tree.
"""
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = HERE.parent / 'packet45-merged3'
OWNER = BASE / '../../stage1/packet3-prep/src'

def validate_baseline_mirror():
    sys.path.insert(0, str(BASE))
    try:
        apply = importlib.import_module('kernel_overlay').apply
        submit = importlib.import_module('submission_overlay').apply_submission_overlay
        closure = importlib.import_module('math_gate').closure
        paths = closure()
        dest = BASE / 'build/checked'
        mapping = {x: dest / x.relative_to(ROOT) for x in paths}
        mapping[(OWNER / 'owner.hpp').resolve()] = mapping[(BASE / 'owner_api.hpp').resolve()]
        hashes = {}
        for source in paths:
            if source == (OWNER / 'owner.hpp').resolve(): continue
            text = submit(source, apply(source, source.read_text()))
            edits = []
            for match in re.finditer(r'\.\s*(parallel_for|single_task)(?:<[^;]*?>)?\s*\(', text):
                capture = re.search(r'\[(?:=|&)?\]\s*(?:\([^;]*?\))?\s*(?:\[\[.*?\]\])?\s*\{', text[match.end():], re.S)
                if not capture or capture.group(0).startswith('[&]'):
                    raise ValueError('unknown mirror kernel capture')
                start = match.end() + capture.start()
                if ';' in text[match.end():start]: raise ValueError('mirror kernel bypass')
                end = match.end() + capture.end()
                depth = 1
                while depth:
                    depth += (text[end] == '{') - (text[end] == '}'); end += 1
                edits.extend([(start, 'packet26::checked('), (end, ')')])
            if len(edits) // 2 != len(re.findall(r'(?:\.|::)\s*(?:parallel_for\w*|single_task)\b', text)):
                raise ValueError('unknown mirror submission')
            for at, value in sorted(edits, reverse=True): text = text[:at] + value + text[at:]
            def include(match):
                name = match[1]
                choices = [source.parent / name, BASE / name, OWNER / name,
                           BASE.parent / 'packet2/kernels' / name, BASE.parent / 'packet2/loader' / name]
                target = next(x.resolve() for x in choices if x.is_file())
                if target == (OWNER / 'owner.hpp').resolve(): target = (BASE / 'owner_api.hpp').resolve()
                return '#include ' + json.dumps(str(mapping[target]))
            text = re.sub(r'^\s*#include\s*"([^"\n]+)"', include, text, flags=re.M)
            expected = '#include ' + json.dumps(str(BASE / 'kernel_guard.hpp')) + '\n#line 1 ' + json.dumps(str(source)) + '\n' + text
            target = mapping[source]
            if target.read_text() != expected: raise ValueError('P45 generated mirror changed: ' + str(target))
            hashes[str(target.relative_to(ROOT))] = hashlib.sha256(expected.encode()).hexdigest()
        return hashes
    finally:
        sys.path.pop(0)

def own_mirror(output):
    """Change include locations only, retaining #line original path identities."""
    output.mkdir(parents=True, exist_ok=True)
    checked = BASE / 'build/checked'
    sources = ['layer_bench.cpp', 'specialized.hpp', 'specialized_cpu_test.cpp', 'fixture_bytes.hpp']
    for name in sources:
        source = HERE / name
        def include(match):
            value = match[1]
            if value in sources: target = output / value
            elif value == 'sycl_operation.hpp': target = checked / (OWNER.resolve() / value).relative_to(ROOT)
            elif value.startswith('../packet45-merged3/'):
                target = checked / (BASE / value.split('../packet45-merged3/', 1)[1]).relative_to(ROOT)
            else: return match[0]
            return '#include ' + json.dumps(str(target))
        text = re.sub(r'^\s*#include\s*"([^"\n]+)"', include, source.read_text(), flags=re.M)
        (output / name).write_text('#line 1 ' + json.dumps(str(source)) + '\n' + text)
