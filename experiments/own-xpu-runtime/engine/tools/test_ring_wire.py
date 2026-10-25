from dataclasses import replace
from hashlib import sha256
import unittest
from pathlib import Path
import struct
import subprocess
import tempfile
import ring_wire as wire
ring=wire.ring

def command(stage=0):
    request=sha256(b'request').digest();before=sha256(b'prefix').digest()
    row=ring.Row(0,2,1,1,17,1,request,before,wire.append_prefix(before,1,17));data=bytes(range(16))
    source=ring.Publication(row,stage-1,9,data,sha256(data).digest()) if stage else None
    return ring.Command(stage,ring.ROW,11,row,True,source=source)

def ack_bytes(c,physical=2,committed=2,pending=0,discarded=(),checked=False):
    return wire.ACK_META.pack(0x5241434b,1,128,int(checked),c.row.epoch,c.row.identity,
          *(discarded+(0,0))[:2],c.stage,c.sequence,c.row_ticket,physical,committed,len(discarded),pending,0,bytes(48))

class WireTests(unittest.TestCase):
    def test_canonical_cpp_codec_accepts_python_and_publishes_exact_bytes(self):
        source = r'''#include "pipeline/ring/wire.hpp"
#include <iostream>
int main(){
 namespace w=ownrt::ring_next::wire;
 w::RowMeta meta;std::array<unsigned char,16> input{},output{};output.fill('x');
 std::cin.read(reinterpret_cast<char*>(&meta),sizeof meta);
 std::cin.read(reinterpret_cast<char*>(input.data()),input.size());
 w::Context context{0,meta.request,1,4,16,97};
 w::Command command{24,17,1,1,1,11,1,0};
 const auto row=w::row(meta,command,context,input);
 const auto pub=w::publication(meta,11,output);
 const auto ack=w::acknowledgment(context,13,row,{1,1,0,{2,3}},true);
 const auto seed=ownrt::ring_next::request_prefix(meta.request,0);
 std::cout.write(reinterpret_cast<const char*>(&pub),sizeof pub);
 std::cout.write(reinterpret_cast<const char*>(&ack),sizeof ack);
 std::cout.write(reinterpret_cast<const char*>(seed.data()),seed.size());
}'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cpp=root/'wire.cpp';binary=root/'wire-test';cpp.write_text(source)
            subprocess.run(['g++','-std=c++20','-O0','-I',str(wire.PLANNING.parent/'src'),str(cpp),'-lcrypto','-o',str(binary)],
                           check=True,capture_output=True,timeout=60)
            original=command(1);metadata,payload=wire.row_metadata(original,final=False,stream_bytes=16)
            result=subprocess.run([str(binary)],input=metadata+payload,capture_output=True,check=True,timeout=5).stdout
        self.assertEqual(len(result),224+128+32)
        wire.validate_publication(result[:224],metadata,11,b'x'*16,final=False,stream_bytes=16)
        second=replace(original,sequence=12,row=replace(original.row,identity=3,parent=2,position=2))
        abort=ring.Command(1,ring.ABORT_SUFFIX,13,original.row,True,11)
        wire.resolution_ack(result[224:352],abort,[original,second],physical=3,committed=1,verify_restore=True)
        self.assertEqual(result[352:],sha256(b'ownrt.ring-request.v1\0'+original.row.request+struct.pack('<Q',0)).digest())

    def test_publication_all_bytes_and_payload_authenticated(self):
        c=command(1);metadata,payload=wire.row_metadata(c,final=False,stream_bytes=16)
        fields=list(wire.ROW_META.unpack(metadata));self.assertEqual(tuple(fields[7:17]),(1,17,1,1,0,0,9,0,16,1))
        output=b'x'*16;fields[3]|=2;fields[14],fields[15],fields[20]=11,16,sha256(output).digest()
        published=wire.ROW_META.pack(*fields)
        wire.validate_publication(published,metadata,11,output,final=False,stream_bytes=16)
        for offset in range(len(published)):
            bad=bytearray(published);bad[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                wire.validate_publication(bytes(bad),metadata,11,output,final=False,stream_bytes=16)
        with self.assertRaises(ValueError):wire.validate_publication(published,metadata,11,b'y'*16,final=False,stream_bytes=16)
    def test_input_lineage_digest_and_final_verified_only(self):
        c=command(1)
        for changed in (replace(c.source,stage=5),replace(c.source,ticket=0),replace(c.source,data=b'x'*16),replace(c.source,row=replace(c.row,identity=3))):
            with self.assertRaises(ValueError):wire.row_metadata(replace(c,source=changed),final=False,stream_bytes=16)
        with self.assertRaises(ValueError):wire.row_metadata(command(),final=True,stream_bytes=16)
        with self.assertRaises(ValueError):wire.row_metadata(replace(command(),row=replace(c.row,after=bytes(32))),final=False,stream_bytes=16)
    def test_resolution_transport_clear_and_initial_tentative(self):
        original=command(1)
        for op in (ring.ACCEPT,ring.ABORT_SUFFIX):
            c=ring.Command(1,op,12,original.row,True,11)
            metadata,payload=wire.row_metadata(c,final=False,stream_bytes=16);fields=wire.ROW_META.unpack(metadata)
            self.assertEqual(fields[3],1);self.assertEqual(fields[12:17],(-1,0,0,0,1))
            self.assertEqual(fields[20],wire.EMPTY_SHA);self.assertEqual(payload,b'')
    def test_accept_and_two_slot_abort_all_ack_bytes(self):
        first=command();second=replace(first,sequence=12,row=replace(first.row,identity=3,parent=2,position=2))
        accept=ring.Command(0,ring.ACCEPT,13,first.row,True,11)
        raw=ack_bytes(accept,physical=3,committed=2,pending=1)
        result=wire.resolution_ack(raw,accept,[first,second],physical=3,committed=1,verify_restore=True)
        self.assertEqual((result.physical,result.committed,result.pending),(3,2,1))
        abort=replace(accept,op=ring.ABORT_SUFFIX);raw=ack_bytes(abort,physical=1,committed=1,discarded=(2,3),checked=True)
        result=wire.resolution_ack(raw,abort,[first,second],physical=3,committed=1,verify_restore=True)
        self.assertEqual(result.discarded,(2,3))
        for offset in range(len(raw)):
            bad=bytearray(raw);bad[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                wire.resolution_ack(bytes(bad),abort,[first,second],physical=3,committed=1,verify_restore=True)
        with self.assertRaises(ValueError):wire.resolution_ack(raw,replace(abort,tentative=False),[first,second],physical=3,committed=1,verify_restore=True)
        with self.assertRaises(ValueError):wire.resolution_ack(raw,abort,[first,second],physical=3,committed=1,verify_restore=False)
