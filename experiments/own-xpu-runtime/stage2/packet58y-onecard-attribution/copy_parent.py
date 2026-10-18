"""One-time symlink-preserving copy; no parent mutation or inherited verdicts."""
import hashlib,json,os,resource,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
SOURCE=P.parent/'packet58v-async-cache'
def main():
    assert shutil.disk_usage('/').free>=25_000_000_000
    assert not (P/'native').exists()
    rows=[]
    def copy(source,dest):
        if source.is_symlink():
            dest.symlink_to(os.readlink(source),target_is_directory=source.is_dir())
            rows.append(dict(path=str(source.relative_to(SOURCE)),symlink=os.readlink(source)))
        elif source.is_dir():
            dest.mkdir(exist_ok=True)
            for child in source.iterdir():
                if child.name!='__pycache__':copy(child,dest/child.name)
        else:
            shutil.copy2(source,dest)
            rows.append(dict(path=str(source.relative_to(SOURCE)),sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    for source in SOURCE.iterdir():
        if source.name in ('build','evidence','READY-FOR-DEVICE.json','build-receipt.json','window.lock',
                           '__pycache__','measure.py','project.py','copy-manifest.json') or source.suffix=='.md':continue
        copy(source,P/source.name)
    (P/'evidence').mkdir();(P/'build').mkdir()
    for name in ('58c-kd','58c-supervisor'):copy(SOURCE/'evidence'/name,P/'evidence'/name)
    copy(SOURCE/'build-receipt.json',P/'lineage/58v-build-receipt.json')
    (P/'copy-manifest.json').write_text(json.dumps(dict(source=str(SOURCE),files=rows,
        preserved_symlinks=sum('symlink' in r for r in rows),evidence_not_inherited=True),indent=2)+'\n')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
