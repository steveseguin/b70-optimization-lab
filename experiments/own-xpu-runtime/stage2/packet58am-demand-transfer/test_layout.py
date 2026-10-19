"""Real checkpoint dispatch coverage, including the old census negative control."""
import json
from pathlib import Path
import unittest
from prepare import P


def expected_commands():
    banks = {}
    for line in (P/'inputs/incident-retrospective/plan.tsv').read_text().splitlines():
        r = line.split()
        if r[2] == 'routed_experts':
            banks.setdefault(int(r[6]), {})[r[1].split('.')[2]] = (int(r[3]), int(r[5]) // 512)
    eligible = [layer for layer, b in banks.items() if
                b['ffn_gate_exps'] == (22, 524800) and b['ffn_up_exps'] == (22, 524800)
                and b['ffn_down_exps'] == (20, 921600)]
    assert len(banks) == 48 and sorted(set(banks)-set(eligible)) == [2]
    return len(banks) + 4 * len(eligible)


def check_census(path):
    count = json.loads(path.read_text())['commands']
    if count != expected_commands():
        raise ValueError(f'wrong-layout kernel captured: {count}, expected {expected_commands()}')


class LayoutRegression(unittest.TestCase):
    def test_old_binary_captured_wrong_layout(self):
        with self.assertRaisesRegex(ValueError, '240, expected 236'):
            check_census(P/'evidence/p58amd-original-incident/demand-prepared-census.json')

    def test_actual_rebuilt_preparation(self):
        for kind in ('smoke', 'v5'):
            check_census(P/f'evidence/preparation-amd-{kind}/demand-prepared-census.json')


if __name__ == '__main__':
    unittest.main()
