#!/usr/bin/env python3
"""Run the unchanged renamed K0 entry against a pure C++ SYCL API mock.

No SYCL implementation is linked or invoked. This checks entry return values,
argument admission and receipt writing; it does not qualify JIT or device work.
Only one compile runs. All temporary source/header/binary/run files are deleted.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
PREFIX = ['nice', '-n', '19', 'ionice', '-c', '3', 'env', 'OMP_NUM_THREADS=2']
MOCK = r"""#pragma once
#include <string>
#include <vector>
namespace sycl {
enum class backend { ext_oneapi_level_zero };
namespace info { enum class device_type { gpu }; }
struct device { unsigned id; };
struct platform {
 static std::vector<platform> get_platforms() { return {{}}; }
 backend get_backend() const { return backend::ext_oneapi_level_zero; }
 std::vector<device> get_devices(info::device_type) const { return {{0},{1},{2},{3}}; }
};
struct context { explicit context(device) {} };
struct kernel_id {
 std::string name;
 const char* get_name() const { return name.c_str(); }
};
inline std::vector<kernel_id> get_kernel_ids() { return {{"mock-kernel-a"},{"mock-kernel-b"}}; }
enum class bundle_state { input };
struct bundle {
 bool has_kernel(const kernel_id&, device) const { return true; }
};
template<bundle_state> bundle get_kernel_bundle(const context&, const std::vector<device>&, const std::vector<kernel_id>&) { return {}; }
inline bundle build(bundle, const std::vector<device>&) { return {}; }
}
"""

def sha(data):
    return hashlib.sha256(data).hexdigest()

def run(argv, **kw):
    return subprocess.run(PREFIX + [str(x) for x in argv], capture_output=True,
                          text=True, **kw)

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    build = HERE/'build'
    build.mkdir(exist_ok=True)
    receipt = {'schema':'own-runtime.packet26.entry-smoke.v1', 'passed':False,
               'device_executed':False, 'real_device_discovery':False,
               'mock_only':True, 'max_compile_jobs':1,
               'source_sha256':sha((HERE/'jit_smoke.cpp').read_bytes()),
               'mock_header_sha256':sha(MOCK.encode()), 'checks':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='entry-smoke-', dir=build) as name:
            tmp = Path(name)
            (tmp/'sycl').mkdir()
            (tmp/'sycl/sycl.hpp').write_text(MOCK)
            source = tmp/'entry.cpp'
            # The production source, including its success return, is unchanged.
            # The quote shim handles only the mock's fixed ASCII error messages.
            source.write_text('#define main packet26_mock_k0_entry\n#include '+
                json.dumps(str(HERE/'jit_smoke.cpp'))+
                '\n#undef main\nnamespace ownrt { std::string quote(const std::string& s) { return std::string(1, char(34))+s+char(34); } }\n'
                'int main(int argc,char** argv) { return packet26_mock_k0_entry(argc,argv); }\n')
            binary = tmp/'k0-entry-cpu-mock'
            command = ['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror=return-type',
                       '-fno-fast-math','-ffp-contract=off','-I'+str(tmp),
                       str(source),'-o',str(binary)]
            compile_result = run(command, timeout=120)
            receipt['compile'] = {'argv':PREFIX+command, 'returncode':compile_result.returncode,
                                  'stdout':compile_result.stdout, 'stderr':compile_result.stderr}
            assert compile_result.returncode == 0, compile_result.stderr
            receipt['binary_sha256'] = sha(binary.read_bytes())
            receipt['mock_translation_unit_sha256'] = sha(source.read_bytes())
            dynamic = run(['readelf','-d',binary], timeout=10)
            assert dynamic.returncode == 0, dynamic.stderr
            receipt['dynamic_dependencies'] = dynamic.stdout
            assert not any(x in dynamic.stdout.lower() for x in
                           ('libsycl','libze_loader','libur_loader','libopencl'))
            cases = [
                ('success', ['--authorized-device-window','--card','0','--cards','1'], 0),
                ('admission_failure', [], 1),
                ('range_failure', ['--authorized-device-window','--card','9','--cards','1'], 1),
            ]
            for label, args, wanted in cases:
                out = tmp/label
                result = run([binary,*args,'--output',out], timeout=10)
                output_file = out/('receipt.json' if wanted == 0 else 'failure.json')
                body = json.loads(output_file.read_text()) if output_file.exists() else None
                row = {'entry':'packet26_mock_k0_entry','case':label,
                       'expected_returncode':wanted,'returncode':result.returncode,
                       'stdout':result.stdout,'stderr':result.stderr,'mock_receipt':body}
                receipt['checks'].append(row)
                assert result.returncode == wanted, row
                assert body is not None and body['passed'] is (wanted == 0), row
                if wanted == 0:
                    assert body['kernel_execution'] is False and body['explicit_allocations'] == 0
                    assert body['cards'] == 1 and body['kernels_per_device'] == 2
            receipt['passed'] = True
    finally:
        receipt['scratch_deleted'] = True
        (HERE/'entry-smoke.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('K0 renamed CPU mock entry: success 0, admission/range failures 1; no device access')

if __name__ == '__main__':
    main()
