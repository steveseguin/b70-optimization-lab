"""Run the packet174 source-delta unit test (passes on this packet, fails on the parent source)."""
import re,subprocess
from build_engine import P,sha,save,limits
def main():
 limits()
 cp=subprocess.run(['/usr/bin/python3','-B','-m','unittest','test_fillkick_delta','-v'],cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
 log=P/'evidence/fillkick-delta-test.log';log.write_text(cp.stdout+cp.stderr)
 n=re.search(r'Ran (\d+) tests',cp.stderr)
 assert cp.returncode==0 and n and int(n.group(1))==4,cp.stderr[-2000:]
 save(P/'evidence/fillkick-delta-test.json',dict(passed=True,device_executed=False,tests=4,log_sha256=sha(log),test_source_sha256=sha(P/'test_fillkick_delta.py'),
  fails_on_parent_source=True,checks=['candidate source has the option, view switch, single kick placement after submitted(), non-blocking device kick, bracket arms and refusal, readout fields',
  'the same checks fail on lineage/p174-parent-native (packet58as)','fill/fill_complete/finish_fills/copy bodies byte-identical to the parent','cache plan/capacity/publication bodies identical; delta touches only four native files']))
 print('PASS delta test')
if __name__=='__main__':main()
