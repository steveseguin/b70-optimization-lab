#!/usr/bin/env python3
"""Hash the final overlay against immutable parent commits, never moving files."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
PARENTS={'packet32':('packet32-pipeline','2e8ec7585c0b0fdd24c7aa07e5752167d6ff2637'),
         'packet36':('packet36-draft','3048343bff'),
         'packet37':('packet37-merged2','3c03e29a4e')}

def source(path):return path.suffix in ('.cpp','.hpp','.py') or path.name=='CMakeLists.txt'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
def git(*args):return subprocess.check_output(['nice','-n','19','ionice','-c','3','git',*args],cwd=ROOT)
def snapshot(directory,commit):
    commit=git('rev-parse',commit+'^{commit}').decode().strip()
    prefix=str((P.parent/directory).relative_to(ROOT))+'/'
    names=[n.decode() for n in git('ls-tree','-r','--name-only','-z',commit,'--',prefix).split(b'\0') if n]
    paths=[n for n in names if source(Path(n)) and '/build/' not in n and '/evidence/' not in n]
    digests={}
    if paths:
        with tarfile.open(fileobj=io.BytesIO(git('archive',commit,'--',*paths)),mode='r:') as archive:
            for member in archive:
                if member.isfile():digests[member.name.removeprefix(prefix)]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    return commit,digests

def main():
    parents={key:snapshot(*spec) for key,spec in PARENTS.items()}
    files={}
    for path in sorted(P.rglob('*')):
        rel=path.relative_to(P)
        if not path.is_file() or any(part in ('build','__pycache__','evidence') for part in rel.parts) or not source(path):continue
        row={'sha256':sha(path)}
        for packet,(commit,digests) in parents.items():
            row[packet+'_sha256']=digests.get(str(rel))
            current=sha(P.parent/PARENTS[packet][0]/rel)
            if current!=row[packet+'_sha256']:row[packet+'_worktree_sha256']=current
        files[str(rel)]=row
    report=dict(base_commit=parents['packet32'][0],packet36_commit=parents['packet36'][0],packet37_commit=parents['packet37'][0],
                comparison='immutable Git parent commits; separately labeled worktree hashes only when newer parent files differ',files=files)
    (P/'source-overlay.json').write_text(json.dumps(report,indent=2)+'\n')
    print(len(files),'source files inventoried against all three immutable parents')
if __name__=='__main__':main()
