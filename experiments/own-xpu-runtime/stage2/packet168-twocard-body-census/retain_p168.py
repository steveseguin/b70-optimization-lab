"""Keep the previous packet's exact evidence before replacing current receipts."""
import gzip,hashlib,io,json,resource,subprocess,tarfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
BASE='b475b618b1b6eb79da08e4f9342735ea2ec6da88'
def main():
    limits()
    prefix=str(P.relative_to(ROOT))+'/'
    listing=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--',prefix],stdin=subprocess.DEVNULL,text=True,cwd=ROOT)
    selected=[s for s in listing.splitlines() if s.startswith(prefix+'evidence/') or s[len(prefix):] in
      ('READY-FOR-DEVICE.json','qualification.json','README.md','CENSUS.md','native_fixture.cpp','native_probe.hpp','census_contract.py','analyze.py')]
    members=[];out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w') as archive:
        for path in selected:
            raw=subprocess.check_output(['git','show',BASE+':'+path],stdin=subprocess.DEVNULL,cwd=ROOT)
            rel=path[len(prefix):];info=tarfile.TarInfo(rel);info.size=len(raw);info.mtime=0
            archive.addfile(info,io.BytesIO(raw));members.append(dict(member=rel,member_digest=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    dest=P/'evidence/packet168-original.tar.gz';dest.write_bytes(gzip.compress(out.getvalue(),mtime=0))
    with tarfile.open(dest) as archive:
        for row in members:
            assert hashlib.sha256(archive.extractfile(row['member']).read()).hexdigest()==row['member_digest']
    save(P/'evidence/packet168-original.json',dict(passed=True,source_commit=BASE,
      archive=str(dest.relative_to(P)),archive_sha256=sha(dest),members=members,
      restore='Extract to a fresh temporary directory; do not overwrite current packet files.'))
    binding=json.loads((P/'oracle-binding.json').read_text())
    if 'files_sha256' in binding:
        binding['source_records']=[dict(repository_path=n,sha256=h) for n,h in binding.pop('files_sha256').items()]
        save(P/'oracle-binding.json',binding)
    print('PASS previous packet receipts retained byte-for-byte:',len(members))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
