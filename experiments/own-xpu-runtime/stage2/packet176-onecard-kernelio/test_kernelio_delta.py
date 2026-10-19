"""Packet176 source-delta test. Passes on this packet's native sources and
fails on the parent packet58as sources (lineage/p176-parent-native, copied from
the git-archive tree before the delta). CPU only; reads text."""
import re,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
OLD=P/'lineage/p176-parent-native/native'  # packet58as text after the copy's path rewrite, before the delta
NAME='packet176-onecard-kernelio'
def norm(text):return text.replace(NAME,'X').replace('packet58as-onecard-spinwait','X')

def body(text,head):
    i=text.index(head);depth=0
    for j in range(text.index('{',i),len(text)):
        depth+=text[j]=='{';depth-=text[j]=='}'
        if depth==0:return text[i:j+1]
    raise AssertionError(head)

def code(text):return '\n'.join(l.split('//')[0] for l in text.splitlines())

def problems(root):
    out=[]
    main=(root/'generated/main.cpp').read_text();bt=(root/'bracket_table.hpp').read_text();probe=(root/'preparation_probe.cpp').read_text()
    hdr=(root/'kernel_io.hpp').read_text() if (root/'kernel_io.hpp').exists() else ''
    if 'std::string foreground_io="copy"; bool foreground_io_supplied=false;' not in main:out.append('default copy option')
    if 'if (k == "--foreground-io")' not in main or '--foreground-io copy|kernel (default:copy)' not in main:out.append('cli/help')
    if 'p176::kernel_io=a.bracket_inputs.empty()?a.foreground_io=="kernel":view.hc=="spin-kio";' not in main:out.append('view switch')
    # Tail: the store kernel is enqueued after the launch loop, before the compute drain.
    if not re.search(r'e->enqueue_ms=e->enqueue_including_wait_ms-\(e->wait_ms-enqueue_wait\);\n\s*if\(kernel_io\)e->tail_store\(\);',main):out.append('tail store placement')
    # Kernel tail: no copy engine between the drain and the host read.
    try:
        ts=code(body(main,'void tail_store()'))
        if 'dev(0).compute(op,ids,{})' not in ts or 'CopyEngine' in ts or 'copy(' in ts.replace('std::memcpy(',''):out.append('tail store is a compute kernel')
        tc=code(body(main,'void tail_check()'))
        if 'stamp==io_stamp' not in tc or 'CopyEngine' in tc:out.append('tail stamp check')
        he=code(body(main,'void head_end()'))
        if 'dev(0).compute(op,ids,{})' not in he or 'CopyEngine' in he or 'wait(' in he:out.append('head load is a compute kernel without host wait')
        sh=code(body(main,'void stage_head(int c,Allocation dst,const void* src,size_t n)'))
        if 'CopyEngine' in sh or 'bracket immutable weight write refused' not in sh:out.append('head staging')
    except ValueError:out.append('kernel io members missing')
    if not re.search(r'if\(kernel_io\)e->tail_check\(\);[^\n]*\n\s*else \{ownrt::CopyEngine copy\(owner\);',main):out.append('copy tail kept for A only')
    if 'if(p176::kernel_io){require(tail_routes_written,"kernel route log missing for this position");' not in main:out.append('route log from kernel')
    for field in ('head_transfer_ms','tail_transfer_ms','route_log_ms','foreground_io'):
        if '\\"'+field+'\\"' not in main:out.append('readout field '+field)
    if 'require(!status,"sticky device error at token "' not in main:out.append('sticky error check')
    k=code(hdr)
    if 'struct TailStore' not in k or 'struct HeadLoad' not in k or 'parallel_for' not in k:out.append('kernel header')
    if re.search(r'\.memcpy\(|\.copy\(|ext_oneapi_submit_barrier|copy_queue|maintenance',k):out.append('kernel header must not issue copy commands')
    if 'v.hc=="spin"||v.hc=="spin-kio"' not in bt or 'views[i].hc==(i%2?"spin-kio":"spin")' not in bt:out.append('bracket arms')
    if '"bracket selects foreground io per view"' not in bt:out.append('bracket refusal')
    if 'p176::kernel_io=view.hc=="spin-kio"' not in probe or 'transport->kernel_tail==24' not in probe:out.append('preparation probe covers B')
    return out

class KernelIoDelta(unittest.TestCase):
    def test_candidate_source(self):
        self.assertEqual(problems(P/'native'),[])
    def test_fails_on_parent_source(self):
        self.assertGreaterEqual(len(problems(OLD)),12)
    def test_backend_and_fill_path_unchanged(self):
        new=norm((P/'native/generated/single_device.cpp').read_text())
        old=norm((OLD/'generated/single_device.cpp').read_text())
        self.assertEqual(new,old)
        main=norm((P/'native/generated/main.cpp').read_text());parent=norm((OLD/'generated/main.cpp').read_text())
        for head in ('void cache_boundary()','void cache_plan_during_position()','void cache_capacity(const std::string& cap)',
                     'void publish_cache_table(const std::vector<p58::Entry>& table)','void upload(int c, Allocation dst, size_t offset, const void *src, size_t n)',
                     'std::vector<uint8_t> readback(int c, Allocation src, size_t n)','void drain()','void prepare_token(int token)'):
            self.assertEqual(body(main,head),body(parent,head),head)
    def test_delta_scope(self):
        touched=sorted({l[6:].strip() for l in (P/'native-delta.patch').read_text().splitlines() if l.startswith('+++ b/')})
        self.assertEqual(touched,['native/bracket_table.hpp','native/generated/main.cpp','native/kernel_io.hpp','native/preparation_probe.cpp'])
if __name__=='__main__':unittest.main()
