import unittest
import cache_budget as budget


class BudgetTests(unittest.TestCase):
    def test_inventory_and_correction(self):
        inv = budget.inventory()
        self.assertEqual(inv['target_nonexpert'], 5_815_529_984)
        self.assertEqual(inv['complete_draft'], 3_354_364_214)
        self.assertEqual(inv['target_kv_index'], 116_391_936)
        self.assertEqual(inv['target_recurrent'], 36 * (48 * 128 * 128 * 2 + 10240 * 3 * 2)
                         + 184320 + 16)

    def test_placement_fits_and_covers_every_layer(self):
        plan = budget.placement()
        self.assertLessEqual(plan['owned_bytes'], plan['limit_bytes'])
        self.assertEqual(len(plan['layers']), 48)
        self.assertTrue(all(len(x['expert_ids']) == x['quota'] and
                            len(set(x['expert_ids'])) == x['quota'] and
                            min(x['expert_ids']) == 0 and max(x['expert_ids']) < 512
                            for x in plan['layers']))
        self.assertTrue(all(x['quota'] in (189, 190) and x['slot_stride_bytes'] % 4096 == 0
                            for x in plan['layers']))
        self.assertGreater(plan['owned_bytes'] + budget.align(budget.ORDINARY), plan['limit_bytes'])
        with self.assertRaises(ValueError):
            budget.placement(1)

    def test_reserve_and_uniform_accounting(self):
        row = budget.budget()
        self.assertGreater(row['margin_after_physical_reserve_bytes'], 0)
        self.assertGreater(row['arena_remaining_bytes'], 0)
        self.assertFalse(row['admitted'])
        scenario = row['hypothetical_uniform']
        self.assertEqual(scenario['expert_bytes_per_target_position'], 949_760_000)
        self.assertAlmostEqual(scenario['cpu_bytes_per_target_position'],
                               949_760_000 * (1 - scenario['byte_hit_fraction']))


if __name__ == '__main__':
    unittest.main()
