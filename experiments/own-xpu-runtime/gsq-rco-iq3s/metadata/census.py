"""Bounded GGUF directory census; never reads alignment padding or tensor bodies."""
from pathlib import Path
import collections, hashlib, importlib.util, json, os, re, resource, stat

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PARSER = ROOT / 'experiments/own-xpu-runtime/stage1/packet1b/loaders/headers.py'
PARSER_SHA = '7503587cb34eb2ed5464ad78d429817e6abc4121c0db81ffc6011da58a54c9fa'
sha = lambda data: hashlib.sha256(data).hexdigest()
assert sha(PARSER.read_bytes()) == PARSER_SHA
spec = importlib.util.spec_from_file_location('admitted_gguf_headers', PARSER)
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
NEW = Path('/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a')
OLD = Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS')
DOWNLOAD = Path('/home/steve/model-downloads/qwen38-gsq-rco-iq3s-20261024')
FORMAT_ROOT = Path('/home/steve/build/flash-next-iq3-baseline-20261010/llama.cpp')
FORMAT_PINS = {'ggml/include/ggml.h':'12ee71f99db7db9b353bc02b1fbb57c344ee17c01ac5fb7952b41a637a747ea9',
 'ggml/src/ggml-common.h':'0061131b615c5721fc88a78feeb22c1f8c450f1c2646a317d80796a653bf595c',
 'ggml/src/ggml-quants.c':'5574a2dccf7c07e75b143733e04a5412d3d8c819e7945f5217a7b83a2b2ff8ab'}
# Additive format knowledge only: do not mutate the frozen parser's type map.
TYPES = dict(H.TYPES, **{})
TYPES[42] = ('Q2_0', 64, 18)  # ggml-common.h: fp16 scale + 16 packed code bytes.



def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class ExactRead:
    """No buffered readahead. Hash exactly the structural bytes requested."""
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()
        self.count = 0

    def read(self, n):
        if n < 0 or self.count + n > H.MAX_HEADER:
            raise ValueError('bounded structural read required')
        data = self.stream.read(n)
        self.digest.update(data)
        self.count += len(data)
        return data


def directory(stream, file_size):
    """Reuse admitted Reader/value decoder; allow opaque tensor type IDs.

    Known types retain exact block/extent validation. Unknown types receive
    only an occupied-directory span, NOT a claimed encoded payload byte size.
    """
    r = H.Reader(stream, file_size)
    if r.read(4) != b'GGUF' or r.number('I') != 3:
        raise ValueError('only little-endian GGUF v3 supported')
    nt, nm = H.integer(r.number('Q'), 0, H.MAX_COUNT), H.integer(r.number('Q'), 0, H.MAX_COUNT)
    meta, kinds = {}, {}
    for _ in range(nm):
        key, kind = r.string(), r.number('I')
        if not key or key in meta:
            raise ValueError('duplicate/empty metadata key')
        meta[key], kinds[key] = H._metadata(r, kind), kind
    canonical(meta)  # Refuse nonfinite values before comparison/hashing.
    align = H.integer(meta.get('general.alignment', 32), 1, 1048576)
    if align & (align - 1) or ('general.alignment' in meta and kinds['general.alignment'] != 4):
        raise ValueError('invalid alignment')
    split = {'split.no', 'split.count', 'split.tensors.count'}
    if split & meta.keys():
        if not split <= meta.keys():
            raise ValueError('incomplete split metadata')
        H.integer(meta['split.no'], 0, H.integer(meta['split.count'], 1, 65535) - 1)
        H.integer(meta['split.tensors.count'], nt)
    tensors = {}
    for _ in range(nt):
        name = r.string()
        if not name or name in tensors:
            raise ValueError('duplicate/empty tensor name')
        rank = H.integer(r.number('I'), 1, 4)
        dims = [r.number('Q') for _ in range(rank)]
        count = H.product(dims)
        kind, offset = r.number('I'), H.integer(r.number('Q'))
        if offset % align:
            raise ValueError('tensor alignment')
        type_name, block, size = TYPES.get(kind, (f'UNKNOWN_{kind}', None, None))
        if block is not None and dims[0] % block:
            raise ValueError('block row violation')
        tensors[name] = dict(type=type_name, type_id=kind, dimensions=dims, shape=dims[::-1],
                             elements=count, data_offset=offset,
                             bytes=H.integer(count // block * size, 1) if block else None)
    data_start = (r.pos + align - 1) // align * align
    if data_start > file_size:
        raise ValueError('truncated data alignment')
    ordered = sorted(tensors.items(), key=lambda item: item[1]['data_offset'])
    for i, (name, t) in enumerate(ordered):
        start = data_start + t['data_offset']
        end = data_start + ordered[i + 1][1]['data_offset'] if i + 1 < len(ordered) else file_size
        if not data_start <= start < end <= file_size:
            raise ValueError('overlap/out-of-file tensor directory span')
        if t['bytes'] is not None and start + t['bytes'] > end:
            raise ValueError('known tensor extent exceeds reserved span')
        t.update(file_offset=start, reserved_span_bytes=end-start,
                 payload_extent_validated=t['bytes'] is not None)
    return dict(metadata=meta, metadata_types=kinds, tensors=tensors, data_start=data_start,
                header_bytes_read=r.pos, file_bytes=file_size)


def summary(value):
    if isinstance(value, list):
        return dict(kind='array', count=len(value), canonical_json_sha256=sha(canonical(value)),
                    first=value[:3], last=value[-3:])
    if isinstance(value, str) and len(value.encode()) > 32768:
        return dict(kind='large-string', utf8_bytes=len(value.encode()), utf8_sha256=sha(value.encode()))
    return value


def role(name):
    return re.sub(r'^blk\.\d+\.', 'blk.*.', name)


def aggregate(tensors):
    types, roles = {}, {}
    for name, t in tensors.items():
        for group, key in ((types, t['type']), (roles, role(name))):
            row = group.setdefault(key, dict(tensors=0, elements=0, known_payload_bytes=0,
                                             opaque_reserved_span_bytes=0, types={}))
            row['tensors'] += 1
            row['elements'] += t['elements']
            row['known_payload_bytes'] += t['bytes'] or 0
            row['opaque_reserved_span_bytes'] += t['reserved_span_bytes'] if t['bytes'] is None else 0
            row['types'][t['type']] = row['types'].get(t['type'], 0) + 1
    return dict(by_type=types, by_projection_role=roles)


def census(root, expected_shards):
    paths = sorted(root.glob('*.gguf'))
    if len(paths) != expected_shards:
        raise ValueError('unexpected shard set')
    parsed, shards, tensors, metadata, kinds = [], [], {}, {}, {}
    for path in paths:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb', buffering=0) as f:
            before = os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('regular shard required')
            reader = ExactRead(f)
            item = directory(reader, before.st_size)
            after = os.fstat(f.fileno())
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if identity(before) != identity(after) or reader.count != item['header_bytes_read']:
                raise ValueError('shard changed/read accounting mismatch')
        parsed.append(item)
        shards.append(dict(path=str(path), stat_identity=list(identity(before)),
                           file_bytes=before.st_size, header_bytes_read=reader.count,
                           header_sha256=reader.digest.hexdigest(), data_start=item['data_start'],
                           tensor_count=len(item['tensors']), split={k:v for k,v in item['metadata'].items() if k.startswith('split.')}))
        for key, value in item['metadata'].items():
            if key.startswith('split.'):
                continue
            if key in metadata and (metadata[key] != value or kinds[key] != item['metadata_types'][key]):
                raise ValueError('cross-shard metadata differs: ' + key)
            metadata[key], kinds[key] = value, item['metadata_types'][key]
        for name, t in item['tensors'].items():
            if name in tensors:
                raise ValueError('duplicate tensor across shards')
            tensors[name] = dict(t, shard=path.name)
    H.gguf_shards(parsed)
    entries = {k:dict(gguf_type_id=kinds[k], value=summary(v), canonical_json_sha256=sha(canonical(v))) for k,v in metadata.items()}
    return dict(root=str(root), shard_count=len(shards), tensor_count=len(tensors),
                file_bytes=sum(s['file_bytes'] for s in shards), header_bytes_read=sum(s['header_bytes_read'] for s in shards),
                shards=shards, metadata=entries, tensors=tensors, **aggregate(tensors))


def compare(old, new):
    a, b = old['tensors'], new['tensors']
    common = sorted(a.keys() & b.keys())
    delta = dict(added_tensors=sorted(b.keys()-a.keys()), removed_tensors=sorted(a.keys()-b.keys()),
                 shape_changes={n:dict(old=a[n]['shape'], new=b[n]['shape']) for n in common if a[n]['shape'] != b[n]['shape']},
                 type_changes={n:dict(old=a[n]['type'], new=b[n]['type']) for n in common if a[n]['type_id'] != b[n]['type_id']})
    am, bm = old['metadata'], new['metadata']
    delta['metadata_added'] = {k:bm[k] for k in sorted(bm.keys()-am.keys())}
    delta['metadata_removed'] = {k:am[k] for k in sorted(am.keys()-bm.keys())}
    delta['metadata_changed'] = {k:dict(old=am[k], new=bm[k]) for k in sorted(am.keys()&bm.keys()) if am[k] != bm[k]}
    delta['metadata_equal_keys'] = [k for k in sorted(am.keys()&bm.keys()) if am[k] == bm[k]]
    delta['type_transition_counts'] = dict(collections.Counter(a[n]['type']+' -> '+b[n]['type'] for n in common))
    return delta


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or not set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32)):
        raise ValueError('helper placement required')
    for name, expected in FORMAT_PINS.items():
        if sha((FORMAT_ROOT/name).read_bytes()) != expected:raise ValueError("format source changed: " + name)
    old, new = census(OLD, 3), census(NEW, 2)
    outputs = {'old-census.json':old, 'new-census.json':new, 'compatibility-delta.json':compare(old,new)}
    for name, value in outputs.items():
        raw=json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode()+b'\n'
        if len(raw)>5*1024**2:
            raise ValueError('artifact budget')
        with (P/name).open('xb') as f:f.write(raw)
    records={str(p):dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size) for p in [DOWNLOAD/'completion.json',DOWNLOAD/'download-plan.json',DOWNLOAD/'hf-metadata.json',DOWNLOAD/'MODEL_CARD.md']}
    receipt=dict(schema='ownrt.gsq-rco.header-census.v1', passed=True,
                 scope='Header/directory only; no payload reads/hashes, model or device execution. Unknown types retain opaque reserved spans, not block-layout claims.',
                 source_sha256={str(PARSER.relative_to(ROOT)):PARSER_SHA,str(Path(__file__).relative_to(ROOT)):sha(Path(__file__).read_bytes())},
                 format_provenance=dict(repository=str(FORMAT_ROOT), recorded_git_head="23b0202a189c44a54625aadcb37a946dd1d6278d", source_sha256=FORMAT_PINS, q2_0=dict(type_id=42, block_elements=64, block_bytes=18, scale="fp16", codes="16 bytes, four 2-bit codes per byte; value=(code-1)*scale")),
                 download_records=records, download_completion=json.loads((DOWNLOAD/'completion.json').read_text()),
                 artifacts={n:dict(sha256=sha((P/n).read_bytes()),bytes=(P/n).stat().st_size) for n in outputs},
                 header_bytes_read=old['header_bytes_read']+new['header_bytes_read'], tensor_payload_bytes_read=0,
                 initial_inherited_parser_refusal=dict(error='unsupported ggml type 42 in blk.1.ffn_down_exps.weight',header_offset=10948774))
    with (P/'receipt.json').open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'passed':True,'old_tensors':old['tensor_count'],'new_tensors':new['tensor_count'],'new_types':new['by_type'],'delta_counts':{k:len(outputs['compatibility-delta.json'][k]) for k in ['added_tensors','removed_tensors','shape_changes','type_changes','metadata_added','metadata_changed']}}))


if __name__ == '__main__':
    main()
