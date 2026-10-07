"""Tiny structural fixtures only: no real capture/model reads or Torch import."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest.mock import patch

import anchor as A

SMALL = {'images':[49,1,1,3], 'video_latent':[1], 'audio_latent':[1], 'waveform':[1]}
LAST_FRAME = struct.pack('<III', 0x80000000, 0, 1)  # -0, +0, smallest subnormal


def archive(shapes=SMALL, nonfinite=False, change_header=None, order=None):
    data, header = bytearray(), {}
    for key in order or shapes:
        shape = shapes[key]
        begin = len(data)
        if key == 'images':
            assert shape == SMALL['images']
            for frame in range(48):
                data.extend(struct.pack('<III', 0x3f800000+frame, 0x40000000+frame, 0x40400000+frame))
            data.extend(LAST_FRAME)
        else:
            data.extend(struct.pack('<I', 0)*math.prod(shape))
        if key == 'images' and nonfinite:
            data[-4:] = struct.pack('<I', 0x7f800001)
        header[key] = {'dtype':'F32', 'shape':shape, 'data_offsets':[begin,len(data)]}
    if change_header:
        change_header(header)
    raw = json.dumps(header, separators=(',',':')).encode()
    raw += b' '*((-len(raw))%8)
    return struct.pack('<Q',len(raw))+raw+data


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root/'continuation111-pass0-chunk0'; self.folder.mkdir()
        self.path = self.folder/'tensors.safetensors'
        self.raw = archive(); self.path.write_bytes(self.raw)
        self.context = {'runtime_manifest_sha256':'a'*64, 'model_verification_sha256':'b'*64,
            'plan_sha256':'c'*64, 'prompt_sha256':'d'*64, 'pass_index':0, 'chunk_index':0,
            'seed':42, 'graph_sha256':'e'*64, 'capture_name':self.folder.name}
    def extract(self, path=None, expected=None):
        return A._extract(path or self.path, expected or A.sha(self.raw), SMALL, 48)
    def small_contract(self):
        # Scope only fixture dimensions; production wrapper always supplies its
        # fixed49x384x640 contract. No146MB sparse files or large arrays exist.
        return patch.multiple(A, SHAPES=SMALL, ANCHOR_SHAPE=[1,1,1,3], FRAME_BYTES=12)

    def test_streamed_whole_capture_hash_and_frame48_exact_signed_zero(self):
        payload, meta = self.extract()
        self.assertEqual(payload, LAST_FRAME)
        self.assertEqual(meta['frame_index'],48)
        self.assertTrue(meta['whole_capture_hash_verified'])
        self.assertFalse(meta['other_tensor_finiteness_verified'])
        self.assertEqual(meta['anchor_sha256'], A.sha(payload))
        with self.assertRaisesRegex(ValueError,'Whole predecessor'):
            self.extract(expected='f'*64)

    def test_distinct_last_frame_nonzero_images_offset_across_tiny_read_blocks(self):
        raw=archive(order=('video_latent','audio_latent','waveform','images'))
        self.path.write_bytes(raw)
        count=struct.unpack('<Q',raw[:8])[0]
        header=json.loads(raw[8:8+count])
        self.assertEqual(header['images']['data_offsets'][0],12)
        # Five-byte reads split every F32 sample and the twelve-byte frame.
        with patch.object(A,'BLOCK',5):
            payload,meta=self.extract(expected=A.sha(raw))
        self.assertEqual(payload,LAST_FRAME)
        self.assertNotEqual(payload,struct.pack('<III',0x3f800000+47,0x40000000+47,0x40400000+47))
        self.assertEqual(meta['anchor_sha256'],A.sha(LAST_FRAME))
        self.assertEqual(meta['capture_sha256'],A.sha(raw))

    def test_public_extractor_refuses_small_wrong_shape_and_legacy25(self):
        with self.assertRaisesRegex(ValueError,'shape/dtype'):
            A.extract_anchor(self.path, A.sha(self.raw))
        shapes = copy.deepcopy(A.SHAPES); shapes['images'][0] = 25
        header={};offset=0
        for key,shape in shapes.items():
            size=math.prod(shape)*4
            header[key]={'dtype':'F32','shape':shape,'data_offsets':[offset,offset+size]};offset+=size
        with self.assertRaisesRegex(ValueError,'shape/dtype'):
            A._header(json.dumps(header).encode(),offset,A.SHAPES)

    def test_wrong_dtype_alias_offsets_extra_tensor_and_nonfinite_refused(self):
        changes = [lambda h:h['images'].update(dtype='BF16'),
                   lambda h:h['waveform'].update(data_offsets=h['audio_latent']['data_offsets']),
                   lambda h:h.update(extra=h['waveform']),
                   lambda h:h['images'].update(shape=[49,1,1,True])]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                raw=archive(change_header=mutate);self.path.write_bytes(raw)
                with self.assertRaises(ValueError):self.extract(expected=A.sha(raw))
        raw=archive(nonfinite=True);self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'Nonfinite anchor'):self.extract(expected=A.sha(raw))
        with self.assertRaisesRegex(ValueError,'Nonfinite JSON'):A.strict_json('{"x":NaN}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):A.strict_json('{"x":1,"x":2}')

    def test_missing_symlink_hardlink_fifo_refused_without_blocking(self):
        with self.assertRaises(FileNotFoundError):self.extract(self.root/'missing')
        link=self.root/'link';link.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError,'Unsafe'):self.extract(link)
        hard=self.root/'hard';os.link(self.path,hard)
        with self.assertRaisesRegex(ValueError,'linked'):self.extract()
        hard.unlink()
        fifo=self.root/'fifo';os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError,'Nonregular'):self.extract(fifo)

    def test_predecessor_changed_during_stream_refuses(self):
        original=A._header
        def mutate(*args):
            value=original(*args)
            with self.path.open('r+b') as f:
                f.seek(-1,2);f.write(b'\x01')
            return value
        with patch.object(A,'_header',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'changed during'):self.extract()

    def test_full_binding_rereads_deleted_changed_and_replaced_predecessor(self):
        with self.small_contract():
            binding=A.bind_predecessor(self.path,A.sha(self.raw),self.context)
            self.assertEqual(A.load_bytes(binding,self.context),LAST_FRAME)
            changed=bytearray(self.raw);changed[-1]^=1;self.path.write_bytes(changed)
            with self.assertRaises(ValueError):A.load_bytes(binding,self.context)
            self.path.unlink()
            with self.assertRaises(FileNotFoundError):A.load_bytes(binding,self.context)
            self.path.write_bytes(self.raw)
            with self.assertRaisesRegex(ValueError,'binding changed'):A.load_bytes(binding,self.context)

    def test_context_binding_cannot_cross_runtime_scene_seed_graph_or_replay(self):
        with self.small_contract():
            binding=A.bind_predecessor(self.path,A.sha(self.raw),self.context)
            for key in ('runtime_manifest_sha256','model_verification_sha256','plan_sha256','prompt_sha256','graph_sha256','seed','pass_index'):
                changed=copy.deepcopy(binding)
                changed['context'][key]=43 if key=='seed' else 1 if key=='pass_index' else 'f'*64
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'lineage'):
                    A.load_bytes(changed,self.context)
            for key,value in [('anchor_sha256','f'*64),('frame_index',24),('dtype','BF16')]:
                changed=copy.deepcopy(binding);changed[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):A.load_bytes(changed,self.context)

    def test_owned_clone_outlives_predecessor_and_does_not_alias_temporary(self):
        captures=[]
        class Tensor:
            def __init__(self,buf,dtype,shape=None):self.buf,self.dtype,self.shape=buf,dtype,shape
            def reshape(self,*shape):self.shape=shape;return self
            def clone(self):return Tensor(bytearray(self.buf),self.dtype,self.shape)
        def frombuffer(buf,dtype):
            self.assertEqual(dtype,'F32');captures.append(buf);return Tensor(buf,dtype)
        fake=types.SimpleNamespace(float32='F32',frombuffer=frombuffer)
        with self.small_contract():
            binding=A.bind_predecessor(self.path,A.sha(self.raw),self.context)
            image=A.load_image(binding,self.context,fake)
            self.assertEqual(image.shape,(1,1,1,3));self.assertEqual(image.dtype,'F32')
            self.assertEqual(bytes(image.buf),LAST_FRAME)
            before=bytes(image.buf);captures[0][0]=99;self.path.unlink()
            self.assertEqual(bytes(image.buf),before)
            with self.assertRaises(FileNotFoundError):A.load_image(binding,self.context,fake)
        self.assertNotIn('torch',__import__('sys').modules)


if __name__ == '__main__':unittest.main()
