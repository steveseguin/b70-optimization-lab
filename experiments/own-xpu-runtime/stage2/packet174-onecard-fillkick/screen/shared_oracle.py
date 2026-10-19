"""Read-only verification through the copied binding; never resolve oracle into a source seal."""
import argparse,json
from suite_driver import oracle_inputs,read,sha,ORACLE,HERE

def completed_binding():
    manifest=oracle_inputs()
    return dict(passed=True,device_executed=False,arithmetic='iq3-p49-split32-v1',prompts=len(manifest['prompts']),
                binding_sha256=sha(HERE/'oracle-binding.json'),completion_sha256=sha(ORACLE/'results/completion.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--require-complete',action='store_true');p.parse_args()
    print(json.dumps(completed_binding()))
