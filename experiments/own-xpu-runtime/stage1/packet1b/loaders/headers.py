"""Header-only readers. Never read tensor payload, mmap, pickle or model code.

GGUF v3 little endian only. The format specification is linked in README.md.
The limits here are deliberate admission limits, not GGUF format maxima.
"""
import json
import math
import struct
from pathlib import Path

MAX_HEADER = 32 * 1024 * 1024
MAX_COUNT = 1000000
MAX_BYTES = (1 << 63) - 1
# ggml type ID: (name, elements/block, bytes/block); no filename inference.
TYPES = {0: ('F32',1,4), 1: ('F16',1,2), 30: ('BF16',1,2), 8: ('Q8_0',32,34),
         11: ('Q3_K',256,110), 12: ('Q4_K',256,144),
         13: ('Q5_K',256,176), 14: ('Q6_K',256,210),
         18: ('IQ3_XXS',256,98), 20: ('IQ4_NL',32,18),
         21: ('IQ3_S',256,110), 22: ('IQ2_S',256,82), 23: ('IQ4_XS',256,136)}
DTYPES = {'BF16':2, 'F8_E4M3':1}


def integer(n, minimum=0, maximum=MAX_BYTES):
    if type(n) is not int or not minimum <= n <= maximum:
        raise ValueError('integer outside admission bounds')
    return n


def product(shape):
    if not isinstance(shape,list) or not 1 <= len(shape) <= 8:
        raise ValueError('invalid rank')
    p = 1
    for n in shape:
        p *= integer(n,1)
        integer(p,1)
    return p


def unique_pairs(pairs):
    out = {}
    for k,v in pairs:
        if k in out:
            raise ValueError('duplicate JSON key')
        out[k] = v
    return out


class Reader:
    def __init__(self, stream, file_size, limit=MAX_HEADER):
        self.stream, self.size, self.limit, self.pos = stream, integer(file_size), limit, 0

    def read(self,n):
        integer(n)
        if self.pos+n > min(self.size,self.limit):
            raise ValueError('truncated or oversized header')
        b = self.stream.read(n)
        if len(b) != n:
            raise ValueError('truncated header')
        self.pos += n
        return b

    def guarantee(self, n):
        """Optional range-stream hint: at least n header bytes remain here.

        Only structural lower bounds, never alignment or payload bytes. Normal
        local streams ignore this; remote streams may batch within this bound.
        """
        integer(n)
        if hasattr(self.stream, 'guarantee_header'):
            self.stream.guarantee_header(min(self.pos+n, self.size, self.limit))

    def number(self,fmt):
        return struct.unpack('<'+fmt,self.read(struct.calcsize('<'+fmt)))[0]

    def string(self):
        n = integer(self.number('Q'),0,MAX_HEADER)
        try:
            return self.read(n).decode('utf-8')
        except UnicodeDecodeError as e:
            raise ValueError('invalid UTF-8') from e


def safetensors_header(stream, file_size):
    """Read exactly length prefix + JSON; validate full payload extent by size."""
    r = Reader(stream,file_size,MAX_HEADER+8)
    n = integer(r.number('Q'),2,MAX_HEADER)
    raw = r.read(n)
    if not raw.startswith(b'{'):
        raise ValueError('header must start with object')
    try:
        header = json.loads(raw,object_pairs_hook=unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('JSON constant')))
    except (UnicodeDecodeError,json.JSONDecodeError) as e:
        raise ValueError('invalid JSON') from e
    if not isinstance(header,dict):
        raise ValueError('object required')
    tensors, intervals = {}, []
    for name,t in header.items():
        if name == '__metadata__':
            if not isinstance(t,dict) or any(not isinstance(v,str) for v in t.values()):
                raise ValueError('metadata must map strings to strings')
            continue
        if not name or not isinstance(t,dict) or set(t) != {'dtype','shape','data_offsets'}:
            raise ValueError('invalid tensor description')
        if t['dtype'] not in DTYPES:
            raise ValueError('unsupported storage dtype')
        length = product(t['shape']) * DTYPES[t['dtype']]
        integer(length,1)
        off = t['data_offsets']
        if not isinstance(off,list) or len(off) != 2:
            raise ValueError('offset pair required')
        start,end = (integer(v) for v in off)
        if end-start != length or end > file_size-r.pos:
            raise ValueError('tensor byte extent')
        tensors[name] = dict(t,bytes=length,file_offsets=[r.pos+start,r.pos+end])
        intervals.append((start,end))
    cursor = 0
    for start,end in sorted(intervals):
        if start != cursor:
            raise ValueError('overlap or gap')
        cursor = end
    if cursor != file_size-r.pos:
        raise ValueError('trailing or missing payload')
    return {'tensors':tensors,'header_and_prefix_bytes':r.pos,'file_bytes':file_size}


def validate_contract(parsed, shard, contract):
    """Exact packet-1 shard/name/dtype/shape/offset/byte and scale-pair check."""
    records = contract['tensors']
    all_t = {t['name']:t for t in records}
    if len(all_t) != len(records):
        raise ValueError('duplicate contract tensor')
    shards = {s['file']:s for s in contract['shards']}
    if len(shards) != len(contract['shards']) or shard not in shards:
        raise ValueError('unknown/duplicate contract shard')
    info = shards[shard]
    for field in ('file_bytes','header_and_prefix_bytes'):
        if parsed[field] != info[field]:
            raise ValueError('shard byte identity differs')
    expected = {n:t for n,t in all_t.items() if t['shard']==shard}
    if set(parsed['tensors']) != set(expected):
        raise ValueError('tensor coverage differs')
    for n,t in expected.items():
        for field in ('shape','dtype','data_offsets','file_offsets','bytes'):
            if parsed['tensors'][n][field] != t[field]:
                raise ValueError('tensor contract differs: '+n+' '+field)
        if t['dtype']=='F8_E4M3':
            fmt = t['format']
            scale = all_t.get(fmt.get('scale_tensor'))
            if fmt.get('block_shape') != [128,128] or fmt.get('scale_dtype') != 'BF16' or len(t['shape']) != 2 or scale is None or scale['dtype'] != 'BF16' or scale['shape'] != [(d+127)//128 for d in t['shape']] or scale['format'].get('weight_tensor') != n:
                raise ValueError('FP8 scale contract differs')
    return parsed


def safetensors_shards(paths, contract):
    """Validate an explicitly supplied complete shard mapping; never discover files.

    This entry point is for packet 2 after admission. Packet 1b uses only
    synthetic files/retained metadata. No payload hashes are authenticated.
    """
    if set(paths) != {s['file'] for s in contract['shards']}:
        raise ValueError('shard coverage differs')
    result = {}
    for shard,path in paths.items():
        if Path(shard).name != shard:
            raise ValueError('unsafe shard name')
        with open(path,'rb') as f:
            size = f.seek(0,2)
            f.seek(0)
            result[shard] = validate_contract(safetensors_header(f,size),shard,contract)
    return result


def _metadata(r,kind,depth=0):
    scalar = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'B',10:'Q',11:'q',12:'d'}
    if kind in scalar:
        v = r.number(scalar[kind])
        if kind==7 and v not in (0,1):
            raise ValueError('invalid bool')
        return bool(v) if kind==7 else v
    if kind==8:
        return r.string()
    if kind==9 and depth==0:
        subtype, count = r.number('I'), integer(r.number('Q'),0,MAX_COUNT)
        if subtype==9 or subtype not in set(scalar)|{8}:
            raise ValueError('unsupported array element type')
        values = []
        width = 8 if subtype == 8 else struct.calcsize('<'+scalar[subtype])
        for i in range(count):
            r.guarantee((count-i)*width)
            values.append(_metadata(r,subtype,1))
        return values
    raise ValueError('unsupported metadata type/nesting')


def gguf_header(stream, file_size):
    """GGUF v3 LE metadata/tensor directory only, offsets relative to aligned data.

    Stored dimensions are fastest-first; reverse them for a row-major tensor.
    Quant blocks cannot cross the first (row) dimension. Validate all extents,
    alignment, overlap and split metadata without reading any tensor bytes.
    """
    r = Reader(stream,file_size)
    if r.read(4)!=b'GGUF' or r.number('I')!=3:
        raise ValueError('only little-endian GGUF v3 supported')
    nt,nm = integer(r.number('Q'),0,MAX_COUNT),integer(r.number('Q'),0,MAX_COUNT)
    meta, meta_types = {}, {}
    for i in range(nm):
        # Metadata: string length + type + smallest scalar; tensor: string
        # length + ndim + at least one dimension + type + offset (32 bytes).
        r.guarantee((nm-i)*13 + nt*32)
        key,kind = r.string(),r.number('I')
        if not key or key in meta:
            raise ValueError('duplicate/empty metadata key')
        meta[key],meta_types[key] = _metadata(r,kind),kind
    alignment = integer(meta.get('general.alignment',32),1,1048576)
    if alignment & (alignment-1) or ('general.alignment' in meta and meta_types['general.alignment']!=4):
        raise ValueError('invalid alignment')
    split_keys = {'split.no','split.count','split.tensors.count'}
    if split_keys & meta.keys():
        if not split_keys <= meta.keys():
            raise ValueError('incomplete split metadata')
        count = integer(meta['split.count'],1,65535)
        integer(meta['split.no'],0,count-1)
        integer(meta['split.tensors.count'],nt)
    tensors = {}
    for i in range(nt):
        r.guarantee((nt-i)*32)
        name = r.string()
        if not name or name in tensors:
            raise ValueError('duplicate/empty tensor name')
        ndim = integer(r.number('I'),1,4)
        dims = [r.number('Q') for _ in range(ndim)]
        count = product(dims)
        kind,off = r.number('I'),integer(r.number('Q'))
        if kind not in TYPES:
            raise ValueError(f'unsupported ggml type {kind} in {name}')
        type_name,block,size = TYPES[kind]
        if dims[0]%block or off%alignment:
            raise ValueError('block row/alignment violation')
        nbytes = integer(count//block*size,1)
        tensors[name] = {'type':type_name,'type_id':kind,'dimensions':dims,
                         'shape':list(reversed(dims)),'data_offset':off,'bytes':nbytes}
    data_start = (r.pos+alignment-1)//alignment*alignment
    if data_start > file_size:
        raise ValueError('truncated data alignment')
    end = 0
    for t in sorted(tensors.values(),key=lambda t:t['data_offset']):
        off = t['data_offset']
        if off<end or data_start+off+t['bytes']>file_size:
            raise ValueError('overlap/out-of-file tensor')
        end = off+t['bytes']
        t['file_offsets'] = [data_start+off,data_start+end]
    return {'metadata':meta,'metadata_types':meta_types,'tensors':tensors,
            'data_start':data_start,'header_bytes_read':r.pos,'file_bytes':file_size}


def gguf_shards(parsed):
    """Validate split ordinals/counts and globally unique tensor names."""
    if not parsed:
        raise ValueError('no shards')
    names, ordinals = set(),set()
    total = sum(len(p['tensors']) for p in parsed)
    for p in parsed:
        m = p['metadata']
        if len(parsed)>1 or 'split.count' in m:
            if m.get('split.count')!=len(parsed) or m.get('split.tensors.count')!=total or m.get('split.no') in ordinals:
                raise ValueError('split coverage/count mismatch')
            ordinals.add(m['split.no'])
        if names & p['tensors'].keys():
            raise ValueError('duplicate tensor across shards')
        names.update(p['tensors'])
    if ordinals and ordinals!=set(range(len(parsed))):
        raise ValueError('missing split')
    return names
