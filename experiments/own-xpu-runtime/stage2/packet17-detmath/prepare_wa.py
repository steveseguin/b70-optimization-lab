"""CPU-only preparation/seal for bounded, lossless W-A host reference slabs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from device_window import sha, save
from summarize_census import UNARY
P = Path(__file__).resolve().parent
B = P / "build"
R = B / "wa-reference"

def input_identity():
    # Device plumbing and the separate W-B loop do not affect W-A host values.
    source = (P / "census.cpp").read_text().split("int main(int argc", 1)[0]
    source = source.replace('#include "wa_storage.hpp"\n', '')
    return dict(census_host_arithmetic_sha256=hashlib.sha256(source.encode()).hexdigest(),
                sources={name: sha(P / name) for name in ("wa_precompute.cpp", "wa_storage.hpp", "detmath.hpp")},
                fixture_trace_sha256=sha(B / "fixture-inputs.bin"), chunk=262144)

def validate_index(root, chunk=262144):
    done = json.loads((root / 'complete.json').read_text())
    if done.get('complete') is not True or done.get('device_executed') is not False or done.get('chunk') != chunk:
        raise ValueError('incomplete CPU references')
    pilots = [json.loads(line) for line in (root / 'coverage.jsonl').read_text().splitlines()]
    if len(pilots) != len(UNARY) or {p['function'] for p in pilots} != set(UNARY):
        raise ValueError('incomplete coverage selection')
    selection = {p['function']: p['selected_bits'] for p in pilots}
    names = ('expf','logf','sqrtf','rsqrt-plain','reciprocal','sinf','cosf','pow-rope','rsqrt-barrier','rsqrt-corrected','division','mul-add','fma','separate')
    seen = set(); fixture_calls = 0; files = set(); rows = []
    for line in (root / 'index.txt').read_text().splitlines():
        file, op, bits, kind, total, explicit = line.split()
        op, bits, total, explicit = map(int, (op, bits, total, explicit))
        if Path(file).name != file or '..' in file or not 0 <= op < len(names) or not (root / file).is_file():
            raise ValueError('invalid reference path/op')
        key = (kind, op)
        if key in seen or total <= 0 or explicit not in (0, 1):
            raise ValueError('duplicate/invalid reference coverage')
        seen.add(key); files.add(root / file)
        if kind in ('native-exhaustive','native-stratified'):
            if names[op] not in selection or bits != selection[names[op]] or bits not in (28,32) or total != 1 << bits or explicit or kind != ('native-exhaustive' if bits == 32 else 'native-stratified'):
                raise ValueError('unary coverage changed')
        elif kind == 'triples':
            if op not in range(10,14) or total != 1 << 26 or not explicit: raise ValueError('triple coverage')
        elif kind == 'rope-arguments':
            if op != 7 or total != 3*32*151 or not explicit: raise ValueError('RoPE coverage')
        elif kind == 'actual-fixture-inputs':
            if not explicit: raise ValueError('fixture operands missing')
            fixture_calls += total
        elif kind == 'precision-probe':
            if op not in (10,2,3,8,9) or total != 65536 or not explicit: raise ValueError('probe coverage')
        else: raise ValueError('unknown reference kind')
        rows.append(dict(file=file, op=op, bits=bits, kind=kind, count=total, explicit_args=bool(explicit)))
    required = {(('native-exhaustive' if selection[name] == 32 else 'native-stratified'),names.index(name)) for name in UNARY}
    required |= {('triples', op) for op in range(10,14)} | {('precision-probe', op) for op in (10,2,3,8,9)} | {('rope-arguments',7)}
    if not required <= seen or fixture_calls != done['fixture_calls'] or fixture_calls <= 0:
        raise ValueError('incomplete reference coverage')
    return rows, files, pilots

def seal():
    identity = json.loads((B / 'wa-generator-identity.json').read_text())
    if identity['inputs'] != input_identity() or identity['binary_sha256'] != sha(B / 'wa-precompute'):
        raise ValueError('W-A generator identity changed')
    rows, files, pilots = validate_index(R)
    binary = B / 'native/wa-verify'
    deps = subprocess.check_output(['readelf','-d',str(binary)], text=True)
    if any(x in deps for x in ('libsycl','ze_loader','OpenCL')): raise ValueError('verifier is not CPU-only')
    subprocess.run([str(binary),'--self-test'],check=True)
    started = time.monotonic()
    verification = json.loads(subprocess.check_output([str(binary),str(R),'262144'],text=True))
    verification['wall_seconds'] = time.monotonic() - started
    if verification.get('passed') is not True: raise ValueError('host slab readback failed')
    files |= {R / name for name in ('index.txt','coverage.jsonl','complete.json')}
    receipt = dict(schema='packet17.wa-host-references.v1', complete=True, device_executed=False,
                   generator=identity, readback=verification, verifier_sha256=sha(binary), threads=1, chunk=262144, encoding='per-slab uint32 delta byte planes + zlib level 1; little endian',
                   coverage=rows, pilots=pilots, stored_bytes=sum(f.stat().st_size for f in files),
                   hashes={str(f.relative_to(P)):sha(f) for f in sorted(files)})
    save(P / 'wa-reference-receipt.json', receipt)
    print(json.dumps(dict(complete=True, device_executed=False, files=len(files), stored_bytes=receipt['stored_bytes'])))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--precompute', action='store_true'); args = ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    if args.precompute:
        if R.exists(): raise ValueError('fresh reference directory required; preserve existing evidence')
        binary = B / 'native/wa-precompute'
        deps = subprocess.check_output(['readelf','-d',str(binary)], text=True)
        if any(x in deps for x in ('libsycl','ze_loader','OpenCL')): raise ValueError('host generator links a device library')
        subprocess.run([str(B/'native/wa-verify'),'--self-test'],check=True)
        import shutil
        shutil.copy2(binary, B / 'wa-precompute')
        save(B / 'wa-generator-identity.json', dict(inputs=input_identity(), binary_sha256=sha(B / 'wa-precompute'),
                                                  command=[str(B / 'wa-precompute'),str(R),str(B / 'fixture-inputs.bin'),'262144'],
                                                  compiler='IntelLLVM 2026.0; original W-A host flags, no -mfma, HOST_ONLY',
                                                  compile_flags=(B / 'native/CMakeFiles/wa-precompute.dir/flags.make').read_text(),
                                                  census_source_sha256=sha(P/'census.cpp')))
        subprocess.run([str(B / 'wa-precompute'),str(R),str(B / 'fixture-inputs.bin'),'262144'], check=True)
    seal()
if __name__ == '__main__': main()
