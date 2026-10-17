#!/usr/bin/env python3
"""CPU engine build using a private remap of inherited validation includes."""
import json,os
from pathlib import Path
import build

def main():
    if os.getpriority(os.PRIO_PROCESS,0)!=19:raise SystemExit('nice19 required')
    if not os.sched_getaffinity(0)<=set(range(4,16))|set(range(20,32)):raise SystemExit('restricted affinity required')
    source=build.BASE/'build/gnu-host/validation';dest=build.B/'gnu-host/validation';dest.mkdir(parents=True,exist_ok=True)
    hashes={}
    for file in source.iterdir():
        if not file.is_file():continue
        data=file.read_text().replace(str(build.BASE/'build/checked'),str(build.B/'checked'))
        (dest/file.name).write_text(data);hashes[file.name]=build.sha(file)
    # build.build records the actual mutated argv, while source manifests and
    # device builder remain untouched. No compiler or execution concurrency.
    run=build.subprocess.run
    def invoke(args,*pargs,**kwargs):
        args[:]=[str(arg).replace(str(source),str(dest)) for arg in args]
        return run(args,*pargs,**kwargs)
    build.subprocess.run=invoke
    build.build('gnu-host')
    path=build.B/'gnu-host/build-receipt.json';record=json.loads(path.read_text())
    record.update(host_builder_sha256=build.sha(Path(__file__)),validation_parent_sha256=hashes,
                  validation_mirror_sha256={f.name:build.sha(f) for f in dest.iterdir() if f.is_file()})
    path.write_text(json.dumps(record,indent=2)+'\n')
if __name__=='__main__':main()
