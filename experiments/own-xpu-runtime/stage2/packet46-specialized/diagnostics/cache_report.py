#!/usr/bin/env python3
"""Offline route accounting for a frozen placement; never trains or changes it."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from validate import check, read_rows, uint, validate


def distribution(values):
    values = sorted(values)
    return dict(count=len(values), mean=sum(values)/len(values),
                p50=values[max(0, math.ceil(.50*len(values))-1)],
                p95=values[max(0, math.ceil(.95*len(values))-1)], maximum=values[-1])


def report(traces, placement):
    layers = placement["placement"]["layers"]
    check(len(layers) == 48 and {r["layer"] for r in layers} == set(range(48)), "cache layer coverage")
    caches, sizes = {}, {}
    for row in layers:
        ids = row["expert_ids"]
        check(isinstance(ids,list) and all(uint(i) and i < 512 for i in ids) and len(set(ids)) == len(ids), "cache IDs")
        check(row["quota"] == len(ids), "cache quota")
        sizes[row["layer"]] = 2_329_600 if row["layer"] == 2 else 1_971_200
        check(row["packed_expert_bytes"] == sizes[row["layer"]], "cache format/size")
        caches[row["layer"]] = set(ids)
    check(traces, "no diagnostic trace")
    headers = [rows[0] for rows in traces]
    check(len({h["rank"] for h in headers}) == len(headers), "duplicate rank trace")
    identity_fields = ("run_id","model_identity","runtime_identity","prompt_sha256","dataset_role")
    check(len({tuple(h[k] for k in identity_fields) for h in headers}) == 1, "different run identities")
    groups = defaultdict(list)
    popularity = defaultdict(Counter)
    coverage = []
    outcomes = Counter()
    for rows in traces:
        validate(rows)
        check(rows[0]["routes"], "route collector disabled")
        resolutions = {(r["request_id"],r["command_sequence"]):r["outcome"] for r in rows if r["kind"] == "resolution"}
        observed = defaultdict(list)
        for row in rows:
            if row["kind"] != "routes": continue
            key = row["request_id"],row["command_sequence"]
            layer = row["layer"]
            missed = sum(expert not in caches[layer] for expert in row["expert_ids"])
            record = dict(layer=layer, misses=missed, miss_bytes=missed*sizes[layer], selected_bytes=10*sizes[layer])
            groups[("all_executed",row["stage"])].append(record)
            groups[("outcome_"+resolutions[key],row["stage"])].append(record)
            observed[key].append(layer)
            if resolutions[key] == "accepted":
                popularity[(row["stage"],layer)].update(row["expert_ids"])
        for key, layer_ids in sorted(observed.items()):
            outcomes[resolutions[key]] += 1
            coverage.append(dict(rank=rows[0]["rank"],request_id=key[0],command_sequence=key[1],
                                 outcome=resolutions[key],observed_layers=sorted(layer_ids)))
    result = []
    for (scope,stage), records in sorted(groups.items()):
        by_layer = defaultdict(list)
        for row in records: by_layer[row["layer"]].append(row["misses"])
        selected = sum(r["selected_bytes"] for r in records)
        missed = sum(r["miss_bytes"] for r in records)
        result.append(dict(scope=scope,stage=stage,layer_evaluations=len(records),
            selected_experts=10*len(records),missing_experts=sum(r["misses"] for r in records),
            selected_packed_bytes=selected,missing_packed_bytes=missed,byte_hit_fraction=(selected-missed)/selected,
            per_layer=[dict(layer=layer,missing_experts=distribution(values)) for layer,values in sorted(by_layer.items())]))
    return dict(schema="ownrt.packet46.cache-route-report.v1", diagnostic_only=True,
                speed_claim_eligible=False, **{key:headers[0][key] for key in identity_fields},
                ranks_present=sorted(h["rank"] for h in headers),
                coverage_definition="observed layer prefixes only; no missing-layer imputation or token-rate extrapolation",
                quantile_definition="nearest-rank empirical quantile of missing experts per observed layer execution",
                scopes=result,command_coverage=coverage,commands_with_routes_by_outcome=dict(outcomes),
                accepted_popularity=[dict(stage=stage,layer=layer,counts={str(k):v for k,v in sorted(counts.items())})
                                     for (stage,layer),counts in sorted(popularity.items())])


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-budget",type=Path,required=True)
    parser.add_argument("trace",nargs="+",type=Path)
    args=parser.parse_args()
    result=report([read_rows(path) for path in args.trace],json.loads(args.cache_budget.read_text()))
    result["source_sha256"]={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [args.cache_budget,*args.trace]}
    print(json.dumps(result,indent=2,sort_keys=True))
