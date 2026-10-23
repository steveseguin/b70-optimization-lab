"""Record the unchanged packet58as spin-wait unit test runs from the one compile turn."""
import json
from build_engine import P,sha,save
def main():
 records=[]
 for tag in ('gnu','intel'):
  log=P/'build'/f'{tag}-wait-test.log';binary=P/'build'/f'{tag}-wait-test'
  assert binary.is_file() and log.is_file()
  records.append(dict(compiler=tag,binary_digest=sha(binary),log_digest=sha(log),passed=True))
 b=json.loads((P/'evidence/build.json').read_text());assert b['passed'] and b['compile_turns']==1
 save(P/'evidence/wait-tests.json',dict(passed=True,device_executed=False,records=records,
  source='native/wait_test.cpp (unchanged packet58as spin wait; built and run in the one compile turn; run() raises on a nonzero exit)'))
 print('PASS wait tests recorded')
if __name__=='__main__':main()
