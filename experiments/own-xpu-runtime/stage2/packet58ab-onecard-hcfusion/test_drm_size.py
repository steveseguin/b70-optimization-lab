import subprocess
import tempfile
import unittest
from pathlib import Path
import device_memory as D

P = Path(__file__).resolve().parent
VALID = [('0', 0), ('1', 1), ('1023', 1023), ('1 KiB', 1024),
         ('1025', 1025), ('1023 KiB', 1024**2-1024),
         ('1048575', 1024**2-1), ('1 MiB', 1024**2),
         ('1048577', 1024**2+1), ('1025 KiB', 1024**2+1024),
         ('1024 MiB', 1024**3), ('32768 MiB', 32*1024**3),
         ('\t29 MiB', 29*1024**2), (str(2**64-1), 2**64-1)]
INVALID = ['', 'KiB', '-1', '+1', '1.0 MiB', '1 GiB', '1 B', '1 KB',
           '1 kib', '1 MiB extra', '1\nMiB', '1\tMiB', '1  MiB',
           '1MiB', '١ KiB', str(2**64), f'{2**54} KiB', f'{2**44} MiB']

class DrmSize(unittest.TestCase):
    def test_units_and_boundaries(self):
        for text, expected in VALID:
            with self.subTest(text=text): self.assertEqual(D.parse_size(text), expected)

    def test_malformed_and_overflow(self):
        for text in INVALID:
            with self.subTest(text=text), self.assertRaises(ValueError): D.parse_size(text)

    def test_native_matches_python(self):
        # Compile only the actual small parser header, never a model or device runtime.
        with tempfile.TemporaryDirectory(prefix='p58xd-parser-') as tmp:
            source = Path(tmp)/'test.cpp'; binary = Path(tmp)/'test'
            source.write_text('#include "'+str(P/'native/drm_size.hpp')+'"\n'
                '#include <iostream>\nint main(int argc,char**argv){try{std::cout<<p58xd::drm_size(argv[1]);}'
                'catch(const std::exception&){return 1;}}\n')
            from build_engine import compiler_turn
            with compiler_turn():
                subprocess.run(['g++','-std=c++20','-O0',str(source),'-o',str(binary)],
                               check=True, stdin=subprocess.DEVNULL, capture_output=True)
            for text, expected in VALID:
                result = subprocess.run([str(binary), text], stdin=subprocess.DEVNULL, capture_output=True, text=True)
                self.assertEqual((result.returncode, result.stdout), (0, str(expected)))
            for text in INVALID:
                self.assertEqual(subprocess.run([str(binary), text], stdin=subprocess.DEVNULL,
                    capture_output=True).returncode, 1, text)

    def test_mixed_units_deduplicate_clients_and_reserve_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp); fd=proc/'7/fdinfo'; fd.mkdir(parents=True)
            template='drm-driver: xe\ndrm-pdev: 0000:23:00.0\ndrm-client-id: {}\ndrm-total-vram0: {}\n'
            for name, client, value in [('1',9,'1024 MiB'),('2',9,'1048576 KiB'),('3',10,'1')]:
                (fd/name).write_text(template.format(client,value))
            row=D.observe([{'pid':7}],proc)
            self.assertEqual((row['clients'],row['bytes']), (2,1024**3+1))
            (fd/'1').unlink(); (fd/'2').unlink()
            for size, expected in [(30_500_000_000,True),(30_500_000_001,False)]:
                (fd/'3').write_text(template.format(10,str(size)))
                self.assertEqual(D.observe([{'pid':7}],proc)['passed'],expected)
