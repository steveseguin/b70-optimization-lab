"""Import actual device paths under the real closed launch environment."""
import importlib.util,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
for name in ['one-card']:
 p=P/name;spec=importlib.util.spec_from_file_location('launch',p/'launch_env.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 results=[]
 for lane in ('A',):
  env=m.environment();env.update(NEOReadDebugKeys='1',FilterBdfPath='0000:23:00.0',ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',ZE_AFFINITY_MASK='0',ONEAPI_DEVICE_SELECTOR='level_zero:0')
  modules=['entry','screen','worker','composition','storage','exec_limits','native_env']
  code="import os,sys,resource,json;resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);sys.path.insert(0,"+repr(str(p))+");import "+','.join(modules)+";assert all(os.environ[k]==v for k,v in native_env.environment("+repr(lane)+").items());print(json.dumps(dict(passed=True,device_executed=False,modules="+repr(modules)+",peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)))"
  cp=subprocess.run(['/usr/bin/python3','-B','-c',code],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True);assert cp.returncode==0,cp.stderr
  r=json.loads(cp.stdout);r.update(environment=env,lane=lane);results.append(r)
 (p/'evidence/device-path-imports.json').write_text(json.dumps(dict(passed=True,device_executed=False,results=results),indent=2)+'\n');print(name,'imports PASS')
