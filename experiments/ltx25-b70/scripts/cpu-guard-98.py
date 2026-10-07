"""Test-only guard: never call real device discovery or permit accelerator allocation."""
import os, sys
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import torch
# CPU test doubles, installed before ComfyUI can query the runtime.
torch.xpu.is_available = lambda: False
torch.xpu.device_count = lambda: 0
torch.xpu.is_initialized = lambda: False
def deny(*args, **kwargs):
    raise RuntimeError('PACKET98_CPU_GUARD: accelerator access forbidden')
for name in ('_lazy_init', 'init', 'synchronize', 'empty_cache', 'mem_get_info', 'set_device', 'current_device', 'get_device_properties', 'get_device_name', 'get_device_capability', 'get_rng_state', 'set_rng_state', 'manual_seed', 'manual_seed_all', 'seed', 'seed_all', 'initial_seed', 'current_stream', 'default_stream', 'set_stream', 'memory_allocated', 'memory_reserved', 'memory_stats'):
    def blocked(*args, **kwargs):
        return deny(*args, **kwargs)
    blocked.__name__ = 'blocked_' + name
    setattr(torch.xpu, name, blocked)
torch.Tensor.xpu = deny
# torch.manual_seed normally broadcasts to accelerator backends even for a CPU test.
# Seed just the CPU default generator instead; the numerical CPU RNG is unchanged.
def cpu_manual_seed(seed):
    return torch.random.default_generator.manual_seed(seed)
torch.manual_seed = cpu_manual_seed
torch.random.manual_seed = cpu_manual_seed

for name in ('empty','empty_strided','zeros','ones','full','rand','randn','randint','tensor','as_tensor','arange','linspace'):
    old = getattr(torch, name)
    def wrap(*args, __fn=old, **kwargs):
        if str(kwargs.get('device', 'cpu')).split(':')[0] not in ('cpu','None','meta'):
            deny()
        return __fn(*args, **kwargs)
    setattr(torch,name,wrap)
old_to=torch.Tensor.to
def safe_to(self,*args,**kwargs):
    device=kwargs.get('device')
    if args and isinstance(args[0],(str,torch.device)):device=args[0]
    if device is not None and str(device).split(':')[0] not in ('cpu','meta'):deny()
    return old_to(self,*args,**kwargs)
torch.Tensor.to=safe_to
torch.set_num_threads(1)
# Fail closed on real checkpoint input and writes outside disposable temporary storage.
def audit(event,args):
    if event == 'open':
        path, mode, flags = args
        if not isinstance(path,(str,bytes)):return
        path=os.path.abspath(os.fsdecode(path))
        write = flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
        if write and not path.startswith('/tmp/') and path not in ('/dev/null',):
            raise PermissionError('PACKET98_CPU_GUARD write outside /tmp: '+path)
        if not write and path.endswith(('.safetensors','.ckpt','.pt','.pth','.bin')) and not path.startswith(('/tmp/','/home/steve/.venvs/')):
            raise PermissionError('PACKET98_CPU_GUARD real weights forbidden: '+path)
    if event in ('os.remove','os.rmdir','os.mkdir','os.rename'):
        for i,p in enumerate(args[:2] if event=='os.rename' else args[:1]):
            if isinstance(p,(str,bytes)):
                p=os.fsdecode(p)
                # unlink/rmdir via a directory descriptor in TemporaryDirectory cleanup.
                fd = args[2+i] if event=='os.rename' else (args[-1] if len(args)>1 else -1)
                if not os.path.isabs(p) and isinstance(fd,int) and fd>=0:
                    p=os.path.join(os.readlink('/proc/self/fd/%d'%fd),p)
                if not os.path.abspath(p).startswith('/tmp/'):
                    raise PermissionError('PACKET98_CPU_GUARD filesystem mutation: '+p)
    if event == 'socket.connect':
        raise PermissionError('PACKET98_CPU_GUARD endpoint access forbidden')
    if event == 'subprocess.Popen':
        exe,argv,cwd,env=args
        base=os.path.basename(str(exe))
        if base.startswith('python'):
            if '-B' not in argv:
                raise PermissionError('PACKET98_CPU_GUARD child Python missing -B')
        elif base not in ('bash','sh','git','uname','getconf'):
            raise PermissionError('PACKET98_CPU_GUARD subprocess forbidden: '+str(exe))
        if base=='git' and any(v in argv for v in ('commit','push','stash','checkout','reset','pull','add')):
            raise PermissionError('PACKET98_CPU_GUARD git mutation forbidden')
sys.addaudithook(audit)
