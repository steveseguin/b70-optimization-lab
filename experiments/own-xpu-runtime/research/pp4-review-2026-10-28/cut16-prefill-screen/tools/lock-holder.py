import fcntl, os, sys, time, json
R='/dev/shm/sc117-long512-cut16-20261028-r1'
paths=[f'/dev/shm/card{c}.lock' for c in (23,27,43,47)]
fds=[]
for p in paths:
    fd=os.open(p,os.O_RDWR)
    try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        open(R+'/locks.status','w').write(json.dumps(dict(held=False,failed=p,pid=os.getpid()))+'\n'); sys.exit(1)
    fds.append(fd)
open(R+'/locks.status','w').write(json.dumps(dict(held=True,paths=paths,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))+'\n')
deadline=time.monotonic()+8*3600
while not os.path.exists(R+'/locks.release') and time.monotonic()<deadline: time.sleep(2)
open(R+'/locks.status','a').write(json.dumps(dict(released=True,by_file=os.path.exists(R+'/locks.release'),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))+'\n')
