"""Host-only regression for the runner's pre-decode EOS boundary.

Compiles the exact runner loop prefix up to the first backend/history access.
The probe records whether that boundary is reached; it has no SYCL/backend,
weights, numerical operators, or simulated model outputs. This is not a GPU
inference/parity test. Run the real runner smoke separately for integration.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


class RunnerInitialEosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shlex.split(os.environ.get("CXX", "c++"))
        if not compiler or not shutil.which(compiler[0]):
            raise RuntimeError("A host C++ compiler is required for the EOS regression")
        source = (Path(__file__).parent / "dsv41-fixtures" / "own_run_v41.cpp").read_text()
        start_marker = "        std::vector<int> out_ids{forced.empty() ? first : forced[0]};"
        stop_marker = "            be.comp_ids.push_back(token_map[cur]);"
        if source.count(start_marker) != 1 or source.count(stop_marker) != 1:
            raise AssertionError("Runner decode boundary changed; update the source extraction")
        prefix = source[source.index(start_marker):source.index(stop_marker)]
        if "for (int step = 1; step < ndecode; ++step) {" not in prefix:
            raise AssertionError("Runner generation loop not found in extracted prefix")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cpp = Path(cls.tmp.name) / "eos_boundary.cpp"
        cls.binary = Path(cls.tmp.name) / "eos_boundary"
        cpp.write_text('''#include <vector>
#include <cstdlib>
#include <cstdio>
int main(int argc, char **argv) {
    if (argc != 6) return 2;
    int first = std::atoi(argv[1]), eos = std::atoi(argv[2]);
    int ndecode = std::atoi(argv[3]);
    std::vector<int> forced;
    if (std::atoi(argv[4])) forced.push_back(std::atoi(argv[5]));
    int reached = 0, input = -99;
''' + prefix + '''
            // Observe the first backend access boundary, then end the probe.
            // No token generation is emulated.
            ++reached;
            input = cur;
            break;
        }
        std::printf("%d %d %zu %d\\n", reached, input, out_ids.size(), out_ids[0]);
}
''')
        subprocess.run(compiler + ["-std=c++17", str(cpp), "-o", str(cls.binary)], check=True,
                       capture_output=True, text=True)

    def probe(self, first, eos=1, count=2, forced=None):
        result = subprocess.run([str(self.binary), str(first), str(eos), str(count),
                                 str(int(forced is not None)), str(forced or 0)],
                                check=True, capture_output=True, text=True)
        return tuple(map(int, result.stdout.split()))

    def test_initial_eos_never_reaches_backend(self):
        self.assertEqual(self.probe(1), (0, -99, 1, 1))

    def test_custom_initial_eos_never_reaches_backend(self):
        self.assertEqual(self.probe(42, eos=42), (0, -99, 1, 42))

    def test_non_eos_reaches_backend(self):
        self.assertEqual(self.probe(42), (1, 42, 1, 42))

    def test_disabled_eos_reaches_backend(self):
        self.assertEqual(self.probe(1, eos=-1), (1, 1, 1, 1))

    def test_forced_eos_preserves_teacher_forcing(self):
        self.assertEqual(self.probe(42, forced=1), (1, 1, 1, 1))

    def test_one_token_limit_never_reaches_backend(self):
        self.assertEqual(self.probe(42, count=1), (0, -99, 1, 42))


if __name__ == "__main__":
    unittest.main()
