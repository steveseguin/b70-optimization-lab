"""Replay owned frozen parent evidence with local readers and the packet49 oracle."""
import hashlib,json,resource,tarfile,tempfile
from pathlib import Path
import suite_driver as D
from readiness_compare import evaluate
P=Path(__file__).resolve().parent
ROOT=P.parents[4]


def main():
    from reseal_boundary import check
    check()
    archive=P/'lineage/58xb-source-snapshot.tar.gz'
    manifest=D.read(P/'lineage/58xb-source-snapshot.json')
    assert D.sha(archive)==manifest['archive_sha256']
    prefix='experiments/own-xpu-runtime/stage2/packet58v-async-cache/evidence/card0-async-a/'
    oracle=D.oracle_inputs()  # Metadata/tokens only; no model payload reads.
    with tempfile.TemporaryDirectory(prefix='p58xc-parent-replay-') as directory:
        root=Path(directory)
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar:
                if not member.name.startswith(prefix):continue
                relative=Path(member.name.removeprefix(prefix))
                assert member.isfile() and not relative.is_absolute() and '..' not in relative.parts
                data=tar.extractfile(member).read()
                assert hashlib.sha256(data).hexdigest()==manifest['members'][member.name]
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        summaries={}
        for arm in ('smoke','overlap'):
            out=root/arm/'WSCREEN/run';recorded=D.read(out/'summary.json');views=[]
            for view in recorded['views']:
                actual=D.summarize(out,'WSCREEN',oracle,view['label'],64 if arm=='smoke' else 128)
                assert actual['requests']==view['requests']
                metric='class_balanced_tok_s_1_100_intervals_after_ttft'
                assert actual[metric]==view[metric]
                actual.update(label=view['label'],view=view['view']);views.append(actual)
            summaries[arm]=views
        assert len(summaries['smoke'])==1 and summaries['smoke'][0]['passed']
        decision=evaluate(summaries['overlap'])
    files=[archive,P/'lineage/58xb-source-snapshot.json',P/'readiness_compare.py',P/'readiness-policy.json',
           P/'maintenance_decision.py',P/'suite_driver.py',P/'suite_metrics.py',P/'oracle-binding.json']
    sources={str(f.relative_to(ROOT)):D.sha(f) for f in files}
    row=dict(passed=True,device_executed=False,default='overlap',parent_bracket_complete=True,
             amendment='packet58xc: owned readers and frozen local evidence; first view exact/reported and outside drift/gain',
             reason='All parent native tokens replayed from the local snapshot against unchanged packet49; no sibling source reads.',
             decision=decision,smoke_passed=True,sources=sources)
    (P/'maintenance-decision.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({k:v for k,v in row.items() if k!='sources'}))


if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));main()
