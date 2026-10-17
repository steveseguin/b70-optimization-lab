#!/usr/bin/env python3
import copy
import unittest
from validate import SCHEMA, validate
from cache_report import report


def fixture():
    base = dict(schema=SCHEMA, rank=0, physical_card=0)
    cmd = dict(request_id=1, command_sequence=2, position=4, token_id=72,
               occupied_context=4, stage="decode", attempt="speculative")
    rows = [dict(base, kind="header", run_id="mock", model_identity="fixture",
                 runtime_identity="fixture", prompt_sha256="0"*64, dataset_role="mock",
                 diagnostic_only=True, speed_claim_eligible=False, routes=True,
                 phases=True, target_experts_per_layer=512, target_top_k=10),
            dict(base, **cmd, kind="routes", layer=3, expert_ids=list(range(10))),
            dict(base, **cmd, kind="phase", layer=3, phase="routing", clock="gpu_event",
                 event_id=5, start_ns=100, end_ns=107, duration_ns=7),
            dict(base, **cmd, kind="resolution", outcome="rejected"),
            dict(base, kind="footer", complete=True)]
    for i, row in enumerate(rows):
        row["record"] = i
    return rows


class Gate(unittest.TestCase):
    def test_valid(self):
        result = validate(fixture())
        self.assertEqual(result["route_layers"], 1)
        self.assertFalse(result["speed_claim_eligible"])

    def test_mutations(self):
        cases = [(0,"speed_claim_eligible",True), (0,"diagnostic_only",False),
                 (0,"routes",False), (0,"phases",False),
                 (1,"expert_ids",[0]*10), (1,"expert_ids",list(range(9))+[512]),
                 (1,"layer",48), (1,"position",True),
                 (2,"duration_ns",8), (2,"clock","wall"), (2,"event_id",0),
                 (3,"token_id",73), (3,"outcome","draft_proposal"),
                 (4,"complete",False)]
        for row, field, value in cases:
            with self.subTest(field=field,value=value):
                rows = fixture(); rows[row][field] = value
                with self.assertRaises(ValueError): validate(rows)

    def test_duplicate_or_unresolved(self):
        for index in (1,2,3):
            rows = fixture(); rows.insert(index,copy.deepcopy(rows[index]))
            for i,row in enumerate(rows): row["record"] = i
            with self.assertRaises(ValueError): validate(rows)
        rows=fixture(); del rows[3]
        for i,row in enumerate(rows): row["record"] = i
        with self.assertRaises(ValueError): validate(rows)

    def test_rejected_and_corrected_are_distinct(self):
        rows=fixture()
        route=copy.deepcopy(rows[1]); resolve=copy.deepcopy(rows[3])
        for row in (route,resolve):
            row.update(command_sequence=3,attempt="corrected",token_id=73)
        resolve["outcome"]="accepted"; route["expert_ids"][0]=511
        rows[-1:-1]=[route,resolve]
        for i,row in enumerate(rows): row["record"] = i
        self.assertEqual(validate(rows)["commands"],2)

    def test_frozen_cache_report(self):
        cache={"placement":{"layers":[dict(layer=i,quota=2,expert_ids=[0,1],
                packed_expert_bytes=2_329_600 if i==2 else 1_971_200) for i in range(48)]}}
        rejected=fixture()
        result=report([rejected],cache)
        self.assertFalse(result["speed_claim_eligible"])
        self.assertEqual(result["accepted_popularity"],[])
        self.assertEqual(result["scopes"][0]["missing_experts"],8)
        self.assertEqual(result["scopes"][0]["missing_packed_bytes"],8*1_971_200)
        accepted=fixture(); accepted[3]["outcome"]="accepted"
        result=report([accepted],cache)
        self.assertEqual(result["accepted_popularity"][0]["counts"]["0"],1)
        self.assertEqual(result["ranks_present"],[0])
        with self.assertRaises(ValueError): report([accepted,accepted],cache)


if __name__ == "__main__":
    unittest.main()
