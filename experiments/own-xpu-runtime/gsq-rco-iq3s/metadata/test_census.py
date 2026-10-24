import io, struct, unittest
import census as C


def string(s):
    b=s.encode();return struct.pack('<Q',len(b))+b


def fixture(tensors=(('x',[64],42,0),), metadata=(), payload=18):
    b=b'GGUF'+struct.pack('<IQQ',3,len(tensors),len(metadata))
    for key,kind,value in metadata:
        b+=string(key)+struct.pack('<I',kind)
        b+=string(value) if kind==8 else struct.pack('<I',value)
    for name,dims,kind,offset in tensors:
        b+=string(name)+struct.pack('<I',len(dims))+struct.pack('<'+'Q'*len(dims),*dims)+struct.pack('<IQ',kind,offset)
    return b,(len(b)+31)//32*32+payload


class Census(unittest.TestCase):
    def parse(self,*a,**kw):
        b,size=fixture(*a,**kw);return C.directory(io.BytesIO(b),size)

    def test_q2_layout_header_only_and_hash_accounting(self):
        b,size=fixture()
        class Guard(io.BytesIO):
            def read(self,n=-1):
                self_assert = self.tell()+n<=len(b) and n>=0
                if not self_assert:raise AssertionError('tensor/padding read')
                return super().read(n)
        r=C.ExactRead(Guard(b));p=C.directory(r,size)
        self.assertEqual(p['tensors']['x']['bytes'],18)
        self.assertEqual(p['tensors']['x']['type'],'Q2_0')
        self.assertEqual(r.count,len(b));self.assertEqual(r.digest.hexdigest(),C.sha(b))
        self.assertNotIn(42,C.H.TYPES)

    def test_unknown_type_is_opaque_not_invented_payload(self):
        p=self.parse(tensors=(('opaque',[64],999,0),),payload=27)['tensors']['opaque']
        self.assertIsNone(p['bytes']);self.assertFalse(p['payload_extent_validated']);self.assertEqual(p['reserved_span_bytes'],27)

    def test_truncation_and_header_limit(self):
        b,size=fixture()
        for cut in (0,4,16,len(b)-1):
            with self.assertRaises(ValueError):C.directory(io.BytesIO(b[:cut]),size)
        b=b'GGUF'+struct.pack('<IQQ',3,0,1)+struct.pack('<Q',C.H.MAX_HEADER+1)
        with self.assertRaises(ValueError):C.directory(io.BytesIO(b),2**40)

    def test_duplicate_names_metadata_and_wrong_alignment(self):
        for args in [dict(tensors=(('x',[64],42,0),('x',[64],42,32)),payload=50),
                     dict(metadata=(('a',4,1),('a',4,2))),
                     dict(tensors=(('x',[64],42,1),))]:
            with self.assertRaises(ValueError):self.parse(**args)

    def test_q2_bad_rows_extent_and_overlaps_refuse(self):
        for args in [dict(tensors=(('x',[63],42,0),)),dict(payload=17),
                     dict(tensors=(('x',[64],42,0),('y',[64],42,0))),
                     dict(tensors=(('x',[128],42,0),('y',[64],42,32)),payload=50)]:
            with self.assertRaises(ValueError):self.parse(**args)

    def test_split_coverage_and_duplicate_cross_shards(self):
        def shard(index,name):return self.parse(tensors=((name,[64],42,0),),metadata=(('split.no',4,index),('split.count',4,2),('split.tensors.count',4,2)))
        self.assertEqual(C.H.gguf_shards([shard(0,'x'),shard(1,'y')]),{'x','y'})
        for items in ([shard(0,'x'),shard(0,'y')],[shard(0,'x'),shard(1,'x')],[shard(0,'x')]):
            with self.assertRaises(ValueError):C.H.gguf_shards(items)

    def test_equal_array_hashes_do_not_depend_on_summary_prefix(self):
        a=list(range(20));b=a.copy();b[10]=999
        sa,sb=C.summary(a),C.summary(b)
        self.assertEqual(sa['first'],sb['first']);self.assertEqual(sa['last'],sb['last'])
        self.assertNotEqual(sa['canonical_json_sha256'],sb['canonical_json_sha256'])

    def test_role_aggregation_preserves_unknown_bytes_scope(self):
        p=self.parse(tensors=(('blk.0.ffn_down_exps.weight',[64],999,0),),payload=27)
        a=C.aggregate(p['tensors'])['by_projection_role']['blk.*.ffn_down_exps.weight']
        self.assertEqual(a['known_payload_bytes'],0);self.assertEqual(a['opaque_reserved_span_bytes'],27)


if __name__=='__main__':unittest.main()
