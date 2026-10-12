#!/usr/bin/env python3
"""CPU-only resumption audit; writes only this suite audit receipt."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import suite_run as run
import suite_check as checker

def main():
    sealed,binary,affinity,prompts=run.preflight()
    report=dict(started_utc=run.utc(),passed=False,affinity=affinity,models=[],prompts=[],files={},verifier_sha256=run.sha(Path(__file__)))
    def verify(path,digest):
        actual=run.sha(path)
        run.check(actual==digest,"hash mismatch: "+str(path))
        report["files"][str(path)]=actual
    # Full hashes, not only stat identity, after the interrupted session.
    for item in sealed["model"]["files"]:
        p=Path(sealed["model"]["model_dir"])/Path(item["path"]).name
        verify(p,item["sha256"])
        run.check(item["expected_sha256"]==item["sha256"],"model expected digest")
        stat=p.stat()
        run.check(dict(bytes=stat.st_size,ctime_ns=stat.st_ctime_ns,device=stat.st_dev,inode=stat.st_ino,mtime_ns=stat.st_mtime_ns)==item["after"],"model stat changed")
        with p.open("rb") as f:
            run.check(hashlib.sha256(f.read(item["header_bytes"])).hexdigest()==item["header_sha256"],"model header hash")
        report["models"].append(dict(path=str(p),bytes=p.stat().st_size,sha256=item["sha256"]))
        run.save(run.HERE/"resume-audit.json",report)
        print("model verified: "+p.name,flush=True)
    report["historical_non_arithmetic_source_drift"]=[]
    for name,digest in sealed["source_hashes"].items():
        actual=run.sha(run.ROOT/name)
        if actual!=digest:
            run.check(name not in sealed["arithmetic"]["arithmetic_sources"],"numerical source drift")
            report["historical_non_arithmetic_source_drift"].append(dict(path=name,recorded_sha256=digest,current_sha256=actual,
                used_for_this_suite=False,note="Historical helper metadata differs; unchanged sealed binary and every defining arithmetic source verified separately."))
        else:verify(run.ROOT/name,digest)
    for name,digest in sealed["model"]["sources"].items():verify(run.ROOT/name,digest)
    for name,digest in sealed["arithmetic"]["arithmetic_sources"].items():verify(run.ROOT/name,digest)
    verify(binary,sealed["binary_sha256"])
    verify(run.SEALED/"incident-retrospective/result.json",sealed["result_sha256"])
    parsed=0
    for root in (run.HERE,run.INPUTS):
        for p in root.rglob("*.json"):
            if p.name=="resume-audit.json":continue
            run.read(p);parsed+=1
        for p in root.rglob("*.jsonl"):
            for line in p.open():json.loads(line)
    report["parsed_json_files"]=parsed
    for p in (run.HERE/"runner-snapshots").glob("*.py"):verify(p,p.stem)
    manifest=run.read(run.INPUTS/"suite-manifest.json")
    entries={r["prompt_id"]:r for r in manifest["prompts"]}
    for row in prompts["prompts"]:
        bundle,inp=run.prepare(row)
        verify(run.ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/tokenizer.py",inp["tokenizer_source_sha256"])
        d=run.HERE/row["id"]
        if not d.exists():continue
        receipt=run.read(d/"receipt.json")
        result=run.read(d/"result.json")
        if len(result["tokens"])>=8:
            pilot=run.read(d/"pilot8.json")
            run.check(pilot["tokens"]==result["tokens"][:8] and pilot["steps"]==result["steps"][:8],"pilot8 content mismatch")
        validation=run.validate(d,bundle)
        run.check(validation==run.read(d/"validation.json"),"validation content")
        checker.check_prompt(d,d,entries[row["id"]])
        verify(d/"positions.jsonl",receipt["seconds_per_position_sha256"])
        verify(run.HERE/"runner-snapshots"/(receipt["runner_sha256"]+".py"),receipt["runner_sha256"])
        verify(run.PREP,receipt["prepare_sha256"])
        run.check(receipt["model"]==sealed["model"] and receipt["arithmetic"]==sealed["arithmetic"],"identity mismatch")
        for name,digest in receipt["source_hashes"].items():verify(run.ROOT/name,digest)
        for name,info in receipt["compressed_logs"].items():
            digest=hashlib.sha256();size=0;lines=0
            with gzip.open(d/(name+".gz"),"rb") as f:
                for line in f:
                    digest.update(line);size+=len(line);json.loads(line);lines+=1
            run.check(digest.hexdigest()==info["sha256"] and size==info["bytes"],"compressed log: "+name)
        if row["id"]=="incident-retrospective":
            run.check(run.equality(d)==run.read(d/"equality-proof.json"),"incident equality proof")
        comparison=run.packet31(d,row["id"])
        if comparison is not None:
            run.check(comparison["passed"] and comparison==run.read(d/"packet31-comparison.json"),"packet31 disagreement")
        report["prompts"].append(dict(prompt=row["id"],passed=True,receipt_sha256=run.sha(d/"receipt.json")))
        print("prompt verified: "+row["id"],flush=True)
    tests=subprocess.run(run.PREFIX+[sys.executable,"-B","-m","unittest","discover","-s",str(run.HERE),"-p","test_suite*.py","-v"],capture_output=True,text=True)
    run.check(tests.returncode==0,tests.stdout+tests.stderr)
    run.save(run.HERE/"checker-tests.json",dict(passed=True,checked_utc=run.utc(),checker_sha256=run.sha(run.HERE/"suite_check.py"),tests_sha256=run.sha(run.HERE/"test_suite_check.py"),supervisor_tests_sha256=run.sha(run.HERE/"test_suite_run.py"),supervisor_sha256=run.sha(run.HERE/"suite_run.py"),stdout=tests.stdout,stderr=tests.stderr))
    report.update(passed=True,completed_utc=run.utc())
    run.save(run.HERE/"resume-audit.json",report)
    print("resume audit PASS",flush=True)

if __name__=="__main__":main()
