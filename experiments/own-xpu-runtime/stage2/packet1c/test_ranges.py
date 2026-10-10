"""CPU synthetic HTTP guards; no network or payload access."""
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fetch_headers',HERE/'fetch-headers.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
sys.path.insert(0,str(HERE.parents[1]/'stage1/packet1b/tests'))
sys.path.insert(0,str(HERE.parents[1]/'stage1/packet1b'))
from test_headers import ggfile, string


class Ranges(unittest.TestCase):
    def test_new_mixed_types_reject_bad_lengths_before_tensor_access(self):
        # This gate exits before torch is used; no tensor library is needed.
        spec=importlib.util.spec_from_file_location('loaders.dequant',HERE.parents[1]/'stage1/packet1b/loaders/dequant.py')
        decoder=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'torch':object()}):spec.loader.exec_module(decoder)
        for kind in ['F32','IQ4_NL','IQ3_S','IQ2_S']:
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'wrong block byte length'):
                decoder.dequant_block(kind,b'')
        with self.assertRaisesRegex(ValueError,'unsupported quantization'):
            decoder.dequant_block('UNKNOWN',b'')

    def test_exact_header_only_with_real_batching(self):
        data=ggfile([('a',[256,512],22,0),('b',[160,2],20,41984)],
            [('tokens',9,struct.pack('<IQ',8,2000)+b''.join(string('word') for _ in range(2000)))])
        expected=f.headers.gguf_header(io.BytesIO(data),len(data))
        limit=expected['header_bytes_read'];calls=[]
        class Response(io.BytesIO):
            def __init__(self,start,end):
                assert end<limit, 'requested padding/payload'
                calls.append((start,end));super().__init__(data[start:end+1])
                self.status=206;self.url='https://example.invalid/header'
                self.headers={'Content-Range':f'bytes {start}-{end}/{len(data)}','Content-Length':str(end-start+1)}
        class Opener:
            def open(self,req,timeout):
                start,end=map(int,req.get_header('Range')[6:].split('-'))
                return Response(start,end)
        with patch.object(f.urllib.request,'build_opener',return_value=Opener()):
            stream=f.RangeStream('https://example.invalid/model',len(data))
            self.assertEqual(f.headers.gguf_header(stream,len(data)),expected)
        self.assertEqual(len(stream.data),limit)
        self.assertLess(len(calls),40)

    def test_bad_response_never_reads_body(self):
        for status,content_range,length,encoding in [(200,'bytes 0-3/100',4,'identity'),
                (206,'bytes 0-3/101',4,'identity'),(206,'bytes 0-3/100',5,'identity'),
                (206,'bytes 0-3/100',4,'gzip')]:
            class Response:
                def __init__(self):
                    self.status=status;self.headers={'Content-Range':content_range,'Content-Length':str(length),'Content-Encoding':encoding}
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self,*args):raise AssertionError('body read')
            class Opener:
                def open(self,*args,**kwargs):return Response()
            with self.subTest(status=status,content_range=content_range,length=length,encoding=encoding),patch.object(f.urllib.request,'build_opener',return_value=Opener()):
                with self.assertRaises(ValueError):f.RangeStream('https://example.invalid/model',100).read(4)

    def test_hard_cap_does_not_issue_more_requests(self):
        stream=f.RangeStream('https://example.invalid/model',100)
        with patch.object(f,'CAP',0),patch.object(f.urllib.request,'build_opener') as opener:
            with self.assertRaisesRegex(ValueError,'hard cap'):stream.read(1)
            opener.assert_not_called()


if __name__=='__main__':unittest.main()
