import copy
import io
import json
import struct
import tempfile
from pathlib import Path
import unittest
from loaders.headers import *


def safefile(header=None,payload=b'\0'*8):
    if header is None:
        header={'w':{'dtype':'BF16','shape':[2,2],'data_offsets':[0,8]}}
    raw = json.dumps(header).encode() if isinstance(header,dict) else header
    return struct.pack('<Q',len(raw))+raw+payload


def string(s):
    b=s.encode(); return struct.pack('<Q',len(b))+b


def ggfile(tensors=None,metadata=(),version=3):
    if tensors is None: tensors=[('w',[32],8,0)]
    header=b'GGUF'+struct.pack('<IQQ',version,len(tensors),len(metadata))
    for key,kind,value in metadata:
        header+=string(key)+struct.pack('<I',kind)+value
    for name,dims,kind,off in tensors:
        header+=string(name)+struct.pack('<I',len(dims))+struct.pack('<'+'Q'*len(dims),*dims)+struct.pack('<IQ',kind,off)
    start=(len(header)+31)//32*32
    length=max([off+math.prod(dims)//TYPES.get(kind,('',1,1))[1]*TYPES.get(kind,('',1,1))[2] for _,dims,kind,off in tensors]+[0])
    return header+b'\0'*(start-len(header)+length)


class Guard(io.BytesIO):
    """Fail if parser attempts even one payload byte."""
    def __init__(self,data,limit): super().__init__(data); self.limit=limit
    def read(self,n=-1):
        if n<0 or self.tell()+n>self.limit: raise AssertionError('payload read')
        return super().read(n)


class SafeHeaders(unittest.TestCase):
    def test_header_only(self):
        b=safefile(); limit=8+struct.unpack('<Q',b[:8])[0]
        p=safetensors_header(Guard(b,limit),len(b))
        self.assertEqual(p['tensors']['w']['shape'],[2,2])

    def test_duplicate_json(self):
        b=safefile(b'{"x":1,"x":2}',b'')
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_truncated_prefix(self):
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b'123'),3)

    def test_header_limit(self):
        b=struct.pack('<Q',MAX_HEADER+1)
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),MAX_HEADER+20)

    def test_truncated_json(self):
        b=struct.pack('<Q',30)+b'{}'
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),100)

    def test_malformed_json(self):
        b=safefile(b'{bad}',b'')
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_nonstring_metadata(self):
        b=safefile({'__metadata__':{'a':1}},b'')
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_overlap(self):
        h={'a':{'dtype':'BF16','shape':[2],'data_offsets':[0,4]},'b':{'dtype':'BF16','shape':[2],'data_offsets':[2,6]}}
        b=safefile(h,b'\0'*6)
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_gap(self):
        b=safefile({'a':{'dtype':'BF16','shape':[2],'data_offsets':[2,6]}},b'\0'*6)
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_wrong_extent(self):
        b=safefile({'a':{'dtype':'BF16','shape':[2],'data_offsets':[0,3]}},b'\0'*3)
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_trailing_payload(self):
        b=safefile(payload=b'\0'*10)
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_bad_dimensions(self):
        for shape in ([0],[True],[-1],[1<<62,4],[1.0],[]):
            b=safefile({'a':{'dtype':'BF16','shape':shape,'data_offsets':[0,2]}},b'00')
            with self.subTest(shape=shape),self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_unsupported_dtype(self):
        b=safefile({'a':{'dtype':'F32','shape':[2],'data_offsets':[0,8]}})
        with self.assertRaises(ValueError): safetensors_header(io.BytesIO(b),len(b))

    def test_all_packet1_headers_without_payload(self):
        root=Path(__file__).resolve().parents[2]/'packet1'
        c=json.loads((root/'tensor-contract.json').read_text())
        count=0
        for shard in c['shards']:
            raw=(root/'metadata/headers'/f"{shard['file']}.json").read_bytes()
            b=struct.pack('<Q',len(raw))+raw
            p=validate_contract(safetensors_header(Guard(b,len(b)),shard['file_bytes']),shard['file'],c)
            count+=len(p['tensors'])
        self.assertEqual(count,1606)

    def synthetic_contract(self):
        b=safefile(); p=safetensors_header(io.BytesIO(b),len(b))
        c={'shards':[dict(file='x.safetensors',file_bytes=len(b),header_and_prefix_bytes=p['header_and_prefix_bytes'])],
           'tensors':[dict(name=n,shard='x.safetensors',format={'kind':'unquantized'},**t) for n,t in p['tensors'].items()]}
        return b,p,c

    def test_contract_mismatch(self):
        b,p,c=self.synthetic_contract()
        for field,value in [('shape',[4]),('dtype','F8_E4M3'),('data_offsets',[1,9]),('bytes',9)]:
            bad=copy.deepcopy(c); bad['tensors'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): validate_contract(p,'x.safetensors',bad)

    def test_contract_duplicate(self):
        b,p,c=self.synthetic_contract(); c['tensors']*=2
        with self.assertRaises(ValueError): validate_contract(p,'x.safetensors',c)

    def test_shard_files_and_coverage(self):
        b,p,c=self.synthetic_contract()
        with tempfile.TemporaryDirectory(prefix='packet1b-') as d:
            f=Path(d)/'x.safetensors'; f.write_bytes(b)
            self.assertIn('x.safetensors',safetensors_shards({'x.safetensors':f},c))
            with self.assertRaises(ValueError): safetensors_shards({},c)

    def test_contract_scale_pair_and_coverage(self):
        root=Path(__file__).resolve().parents[2]/'packet1'
        c=json.loads((root/'tensor-contract.json').read_text())
        shard=c['shards'][0]
        raw=(root/'metadata/headers'/f"{shard['file']}.json").read_bytes()
        p=safetensors_header(io.BytesIO(struct.pack('<Q',len(raw))+raw),shard['file_bytes'])
        index=next(i for i,t in enumerate(c['tensors']) if t['shard']==shard['file'] and t['dtype']=='F8_E4M3')
        for field,value in [('scale_dtype','F32'),('block_shape',[64,64]),('scale_tensor','missing')]:
            bad=copy.deepcopy(c); bad['tensors'][index]['format'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): validate_contract(p,shard['file'],bad)
        bad=copy.deepcopy(p); bad['tensors'].pop(next(iter(bad['tensors'])))
        with self.assertRaises(ValueError): validate_contract(bad,shard['file'],c)


class GGHeaders(unittest.TestCase):
    def parse(self,b): return gguf_header(io.BytesIO(b),len(b))

    def test_remote_structural_hints_never_cross_header(self):
        class HintGuard(Guard):
            def guarantee_header(self, end):
                if end > self.limit:
                    raise AssertionError('hint includes padding or payload')
        metadata = [('strings',9,struct.pack('<IQ',8,3)+string('')+string('abc')+string('x'*800)),
                    ('numbers',9,struct.pack('<IQddd',12,3,1,2,3)), ('last',7,b'\1')]
        for tensors in ([], [('x',[1],0,0)], [('a',[256,2],18,0),('b',[1],0,224)]):
            b = ggfile(tensors,metadata)
            expected = self.parse(b)
            self.assertEqual(gguf_header(HintGuard(b,expected['header_bytes_read']),len(b)),expected)

    def test_every_type_header_only(self):
        for kind,(name,block,size) in TYPES.items():
            b=ggfile([('w',[block,2],kind,0)])
            p=self.parse(b)
            again=gguf_header(Guard(b,p['header_bytes_read']),len(b))
            self.assertEqual(again['tensors']['w']['bytes'],size*2)
            self.assertEqual(again['tensors']['w']['shape'],[2,block])

    def test_version(self):
        with self.assertRaises(ValueError): self.parse(ggfile(version=2))

    def test_truncated(self):
        b=ggfile()
        for n in (0,4,12,24,30,len(b)-1):
            with self.subTest(n=n),self.assertRaises(ValueError): self.parse(b[:n])

    def test_type_unknown(self):
        with self.assertRaises(ValueError): self.parse(ggfile([('w',[32],99,0)]))

    def test_row_block_crossing(self):
        with self.assertRaises(ValueError): self.parse(ggfile([('w',[16,2],8,0)]))

    def test_duplicate_tensor(self):
        with self.assertRaises(ValueError): self.parse(ggfile([('w',[32],8,0),('w',[32],8,64)]))

    def test_overlapping_tensor(self):
        with self.assertRaises(ValueError): self.parse(ggfile([('a',[32],8,0),('b',[32],8,32)]))

    def test_unaligned_tensor(self):
        with self.assertRaises(ValueError): self.parse(ggfile([('w',[32],8,1)]))

    def test_duplicate_metadata(self):
        m=[('x',4,struct.pack('<I',1))]*2
        with self.assertRaises(ValueError): self.parse(ggfile(metadata=m))

    def test_alignment_not_power_two(self):
        with self.assertRaises(ValueError): self.parse(ggfile(metadata=[('general.alignment',4,struct.pack('<I',3))]))

    def test_invalid_bool(self):
        with self.assertRaises(ValueError): self.parse(ggfile(metadata=[('x',7,b'\x02')]))

    def test_all_metadata_scalars_and_array(self):
        m=[('s',8,string('hello')),('bool',7,b'\1'),('arr',9,struct.pack('<IQii',5,2,-2,7))]
        for kind,fmt in [(0,'B'),(1,'b'),(2,'H'),(3,'h'),(4,'I'),(5,'i'),(6,'f'),(10,'Q'),(11,'q'),(12,'d')]:
            m.append((str(kind),kind,struct.pack('<'+fmt,1)))
        p=self.parse(ggfile(metadata=m))
        self.assertEqual(p['metadata']['arr'],[-2,7]); self.assertEqual(p['metadata']['s'],'hello')

    def test_nested_array_rejected(self):
        with self.assertRaises(ValueError): self.parse(ggfile(metadata=[('a',9,struct.pack('<IQ',9,0))]))

    def test_count_limit(self):
        b=b'GGUF'+struct.pack('<IQQ',3,MAX_COUNT+1,0)
        with self.assertRaises(ValueError): self.parse(b)

    def test_dimensions_overflow(self):
        b=bytearray(ggfile([('w',[1,1],1,0)]))
        # 24-byte fixed header, string length/name, rank, then dimensions.
        struct.pack_into('<QQ',b,37,1<<62,8)
        with self.assertRaises(ValueError): self.parse(b)

    def test_invalid_utf8(self):
        b=bytearray(ggfile()); b[32]=255
        with self.assertRaises(ValueError): self.parse(b)

    def split(self,num,name):
        m=[('split.no',2,struct.pack('<H',num)),('split.count',2,struct.pack('<H',2)),('split.tensors.count',5,struct.pack('<i',2))]
        return self.parse(ggfile([(name,[32],8,0)],m))

    def test_split_valid(self):
        self.assertEqual(gguf_shards([self.split(0,'a'),self.split(1,'b')]),{'a','b'})

    def test_split_missing_duplicate_and_tensor_collision(self):
        for p in ([self.split(0,'a')],[self.split(0,'a'),self.split(0,'b')],[self.split(0,'a'),self.split(1,'a')]):
            with self.assertRaises(ValueError): gguf_shards(p)

    def test_incomplete_split_metadata(self):
        with self.assertRaises(ValueError): self.parse(ggfile(metadata=[('split.no',2,struct.pack('<H',0))]))
