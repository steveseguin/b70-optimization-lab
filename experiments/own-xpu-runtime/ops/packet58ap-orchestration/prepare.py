"""Vendor immutable local bytes; never edit or execute the parent packet."""
import hashlib,json,os,shutil
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet58ap-onecard-chain'
AJ=P.parent/'packet58aj-onecard-resident';AM=P.parent/'packet58am-demand-transfer'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
def copy(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b);assert sha(a)==sha(b)
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert not P.exists();P.mkdir();(P/'evidence').mkdir()
    excluded={'build-receipt.json','submission-pins.json','ready.json','READY-FOR-DEVICE.json','parent-binding.json','copy-manifest.json','screen_gate.py','build_engine.py','resident_source.py','native_source.py','prepare.py','preparation_gate.py','restore_build.py','native_cpu_gates.py','resident_gate.py','native_parser_gate.py','screen-reader'}
    for f in AJ.iterdir():
        if f.is_file() and f.name not in excluded and f.suffix in ('.py','.json','.md','.snapshot'):
            copy(f,P/f.name)
    for folder in ('host-admission','selections','frozen-inputs'):
        shutil.copytree(AJ/folder,P/folder,symlinks=False,ignore=shutil.ignore_patterns('__pycache__'))
    for leaf in ('synthetic-lookup-receipt.json',):copy(AJ/'lineage'/leaf,P/'lineage'/leaf)
    for leaf in ('fullshape-submit-cpu.json','postload-allocation-cpu.json','postload-census.json','58c-kd/run/progress.jsonl'):
        copy(AJ/'evidence'/leaf,P/'evidence'/leaf)
    # Rewrite only the new wrapper identity. Vendored source bytes stay original.
    for f in P.glob('*'):
        if f.is_file() and f.suffix in ('.py','.json','.md','.snapshot'):
            t=f.read_text().replace('packet58aj-onecard-resident','packet58ap-onecard-chain').replace('packet58aj-orchestration','packet58ap-orchestration').replace('58aj-a','58ap-a')
            f.write_text(t)
    build=json.loads((AM/'evidence/build.json').read_text())
    assert build['passed'] and not build['device_executed']
    manifest={}
    for leaf,digest in build['sources'].items():
        assert sha(AM/leaf)==digest,leaf
        dest=P/'lineage/demand-sources'/leaf;copy(AM/leaf,dest)
        manifest[str(dest.relative_to(P))]=digest
    for leaf in ('evidence/build.json','RELEASE-AMENDMENT.md','screen/compare_bracket.py','analyze.py','native/preparation_probe.inc'):
        dest=P/'lineage/packet58am'/leaf;copy(AM/leaf,dest);manifest[str(dest.relative_to(P))]=sha(dest)
    copy(ROOT/'notes/2026-10-19-own-runtime-packet58ai.md',P/'lineage/packet58ai-note.md')
    artifacts={}
    for leaf,digest in build['artifacts'].items():
        assert sha(AM/leaf)==digest,leaf
        copy(AM/leaf,P/leaf);artifacts[leaf]=digest
    for leaf in ('build/device/p58-cache-fixtures','build/gnu-host/p58-cache-fixtures','build/gnu-host/fullshape-submit'):
        copy(AJ/leaf,P/leaf);artifacts[leaf]=sha(P/leaf)
    copy(AM/'analyze.py',P/'demand_analyze.py')
    t=(P/'demand_analyze.py').read_text().replace('from packet_io import P,ROOT,AH,sha,save','from pathlib import Path\nP=Path(__file__).resolve().parent\nROOT=P.parents[3]')
    (P/'demand_analyze.py').write_text(t[:t.index('\ndef replay():')])
    save(P/'parent-binding.json',dict(parent=str(AM.relative_to(ROOT)),build_sha256=sha(AM/'evidence/build.json'),sources=manifest,artifacts=artifacts,vendored=True,mutable_parent_required_at_launch=False))
    copy(ROOT/'scripts/packet58_onecard_record_threshold.json',P/'record-threshold.snapshot')
    policy=json.loads((P/'submission-policy.json').read_text());ledger=json.loads((P/'record-threshold.snapshot').read_text())
    policy.update(schema='packet58ap.submission-policy.v1',ledger_sha256=sha(P/'record-threshold.snapshot'),supersedes={k:ledger['records'][-1][k] for k in ('reference_submission','threshold_tok_s')},readiness_amendment='Census release gate superseded by direct smoke/v5 (packet58ai note and RELEASE-AMENDMENT.md). p58ap requires each candidate >=+0.5% over EVERY warm control; all views exact; drift <=3%; A0 warm-up. Bracket numbers are bound in queue readiness at launch.')
    policy['scope'].update(rule='packet58ap.onecard-128-preparation.2026-10-19',authority='Owner packet58ap brief; coordinator submits.')
    save(P/'submission-policy.json',policy)
    save(P/'readiness-policy.json',dict(minimum_relative_rate=1.005,maximum_control_drift=.03,first_view_warmup=True,full_exact_suite_required=True))
    selection=json.loads((P/'runtime-selection.json').read_text());selection.update(demand='bcs-demand-retained32x2');save(P/'runtime-selection.json',selection)
    print(json.dumps(dict(vendored_sources=len(manifest),artifacts=artifacts)))
if __name__=='__main__':main()
