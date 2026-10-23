"""Offline source, dependency and ELF checks. Never invokes the native artifact."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import unittest

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[3]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def elf_sections(path):
    """Read only the fixed ELF64 little-endian section directory and names."""
    with Path(path).open("rb") as source:
        header = source.read(64)
        if header[:6] != b"\x7fELF\x02\x01":
            raise ValueError("expected little-endian ELF64")
        offset = struct.unpack_from("<Q", header, 40)[0]
        size, count, names_index = struct.unpack_from("<HHH", header, 58)
        length = Path(path).stat().st_size
        if size != 64 or not 0 < count < 4096 or not names_index < count or offset + size * count > length:
            raise ValueError("bounded ELF section table")
        source.seek(offset)
        entries = [struct.unpack("<IIQQQQIIQQ", source.read(64)) for _ in range(count)]
        names = entries[names_index]
        if names[4] + names[5] > length or names[5] > 1024 * 1024:
            raise ValueError("bounded ELF section names")
        source.seek(names[4])
        strings = source.read(names[5])
        result = {}
        for entry in entries:
            end = strings.find(b"\0", entry[0])
            if end < 0:
                raise ValueError("invalid ELF section name")
            name = strings[entry[0]:end].decode("ascii")
            result[name] = {"offset": entry[4], "bytes": entry[5], "kind": entry[1]}
        return result


class CompileAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads((P / "evidence/build-compile-only.json").read_text())
        cls.plan = cls.receipt["plan"]

    def test_native_compile_identity_and_precise_flags(self):
        r = self.receipt
        self.assertTrue(r["passed"] and r["compile_only"])
        for name in ("fixture_executed", "device_enumerated", "device_executed", "model_executed"):
            self.assertFalse(r[name])
        compile, link = self.plan["commands"]
        self.assertEqual(compile[0], "/opt/intel/oneapi/compiler/2026.0/bin/icpx")
        self.assertEqual(link[0], compile[0])
        for option in ("-fsycl", "-fno-fast-math", "-ffp-contract=off", "-fdenormal-fp-math=ieee", "-foffload-fp32-prec-div", "-foffload-fp32-prec-sqrt"):
            self.assertIn(option, compile)
        self.assertNotIn("-DOWN_RT_HOST_ONLY", compile)
        self.assertEqual(compile[compile.index("-c") + 1], str(P / "native_fixture.cpp"))
        self.assertEqual(compile[compile.index("-o") + 1], self.plan["object"])
        self.assertEqual(link[link.index("-o") + 1], self.plan["binary"])
        self.assertEqual(self.plan["target"], "device-compile-only")
        self.assertEqual(sha(r["compiler"]["path"]), r["compiler"]["sha256"])

    def test_all_repository_sources_parent_objects_and_logs_current(self):
        r = self.receipt
        for mapping in (r["source_sha256"], self.plan["repository_dependencies"],
                        r["artifact_sha256"], json.loads((P / "parent-pins.json").read_text())):
            for name, expected in mapping.items():
                self.assertEqual(sha(ROOT / name), expected, name)
        self.assertEqual(len(self.plan["repository_dependencies"]), 43)
        self.assertEqual(len(self.plan["objects"]), 33)
        for name, expected in self.plan["objects"].items():
            self.assertEqual(sha(name), expected, name)
        authority = json.loads((P / "authority-inputs.json").read_text())
        for name, expected in authority["source_sha256"].items():
            self.assertEqual(sha(ROOT / name), expected, name)
        for name, expected in authority["inherited_native_p33_objects_sha256"].items():
            self.assertEqual(sha(name), expected, name)
            self.assertEqual(self.plan["objects"][name], expected)

    def test_actual_compiler_dependency_inventory_matches_receipt(self):
        text = Path(self.plan["depfile"]).read_text().replace("\\\n", " ")
        files = {str(Path(item).resolve().relative_to(ROOT)) for item in shlex.split(text.split(":", 1)[1])}
        self.assertEqual(files, set(self.plan["repository_dependencies"]))
        for name in ("native_fixture.cpp", "paired_sycl.hpp", "selected_headers.hpp"):
            self.assertIn(str((P / name).relative_to(ROOT)), files)
        for suffix in ("p33_candidates.hpp", "p33_submit.hpp", "sycl_operation.hpp", "prepared_submission.hpp"):
            self.assertTrue(any(name.endswith("/" + suffix) for name in files), suffix)

    def test_actual_elf_offload_and_both_compiled_kernel_images(self):
        r = self.receipt
        for name in ("binary", "object"):
            self.assertEqual(sha(self.plan[name]), self.plan[name + "_sha256"])
            sections = elf_sections(self.plan[name])
            offload = [(key, value) for key, value in sections.items() if key.startswith("__CLANG_OFFLOAD_BUNDLE__sycl-spir64")]
            self.assertTrue(offload, name)
            self.assertTrue(all(value["bytes"] > 0 for _, value in offload))
        image = r["offline_image"]
        self.assertEqual(set(image["targets"]), {"sycl-spir64-unknown-unknown", "host-x86_64-unknown-linux-gnu"})
        bitcode = P / "build/native/pair-device.bc"
        self.assertEqual(bitcode.read_bytes()[:4], b"BC\xc0\xde")
        self.assertEqual(bitcode.stat().st_size, image["bitcode_bytes"])
        self.assertEqual(sha(bitcode), image["bitcode_sha256"])
        expected = {"_ZTSN4p20816NativePairKernelILj10240EEE", "_ZTSN4p20816NativePairKernelILj6144EEE"}
        self.assertEqual(set(image["kernel_entries"]), expected)
        actual = []
        for name, digest in image["symbol_files"].items():
            self.assertEqual(sha(ROOT / name), digest)
            actual.extend((ROOT / name).read_text().splitlines())
        self.assertEqual(set(actual), expected)
        symbols = next(ROOT / name for name in r["artifact_sha256"] if name.endswith("/native-symbols.log"))
        self.assertIn(" T p208_future_qualification", symbols.read_text())
        self.assertIn("__sycl", symbols.read_text())

    def test_reviewed_seven_argument_and_ordered_queue_source_contract(self):
        # Structural regression only; this does not execute admission or a queue.
        text = (P / "paired_sycl.hpp").read_text()
        self.assertRegex(text, r"PairOperation\s+final\s*:\s*ownrt::SyclOperation")
        self.assertIn("#ifdef OWN_RT_HOST_ONLY\n#error", text)
        self.assertIn("std::array<ownrt::Allocation,7> ids{a.w,a.x,b.x,a.y,b.y,a.workspace,b.workspace}", text)
        self.assertIn("require(deps.empty()", text)
        self.assertIn("q.has_property<sycl::property::queue::in_order>()", text)
        self.assertIn("a.x!=b.x && a.w!=a.x && a.w!=b.x", text)
        self.assertIn("ownrt::prepared_submit(q,[=]", text)
        self.assertIn("[[sycl::reqd_sub_group_size(32)]]", text)
        self.assertNotIn("reduce_over_group", text)
        self.assertIn("for(unsigned width=1;width<32;width*=2)", text)

    def test_native_serial_authority_and_nonexecuting_main(self):
        dispatch = json.loads((P.parent / "packet181-session-swap-v3/one-card/dispatch.json").read_text())
        self.assertEqual(dispatch["gemv"]["gdn.qkv"], "p33.dense.segment")
        self.assertEqual(dispatch["gemv"]["gdn.z"], "p33.dense.segment")
        source = (P / "native_fixture.cpp").read_text()
        self.assertIn('p33::submit(d,{m},"p33.dense.segment",false,6)', source)
        self.assertIn("p33::dense_lane<iq3::Type::Q6_K,2560>", source)
        main = source[source.index("int main("):]
        self.assertIn("return 64;", main)
        self.assertNotIn("p208_future_qualification", main)
        self.assertNotIn("make_sycl_device", main)


if __name__ == "__main__":
    unittest.main()
