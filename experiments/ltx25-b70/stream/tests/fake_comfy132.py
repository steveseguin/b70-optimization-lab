#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Packet132 synthetic CPU protocol; waveform/admission fixtures are not GPU evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy131.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy131.py')), 'exec'))
source = source.replace('assert c.PACKET == 131', 'assert c.PACKET == 132')
source = source.replace('stream131-s', 'stream132-s')
source = source.replace("ap.add_argument('--cone-graph-memory'", "ap.add_argument('--audio-residency', choices=('legacy', 'xpu2'), default='legacy')\nap.add_argument('--cone-capture-reserve', choices=('parent',), default='parent')\nap.add_argument('--cone-graph-memory'")
source = source.replace("SERVER_OPTIONS.update(cone_graph_memory=", "SERVER_OPTIONS.update(audio_residency=a.audio_residency, cone_capture_reserve=a.cone_capture_reserve, cone_graph_memory=")
source = source.replace("'cone_graph_memory': True,", "'cone_graph_memory': True, 'audio_residency': True, 'cone_capture_reserve': True,")
source = source.replace('def make_decode_record(job, t):', """def audio_evidence132(record):
    record.update(audio_residency=a.audio_residency, audio_device='xpu:2' if a.audio_residency=='xpu2' else 'xpu:3', audio_residency_evidence=None)
    if a.audio_residency=='legacy':
        return
    import audio_residency132 as ar
    eager=record['kind']=='qualify-eager'
    released=dict(device='cpu', active=False, calls=record['chunk_index']+1 if eager else 3,
                  resident_bytes_on_xpu3=0, weight_sha256='a'*64)
    def workspace(device, resident=0):
        return dict(before=ar.check_workspace(24*2**30,device,True,resident),
                    after=ar.check_workspace(24*2**30,device,False))
    row=dict(mode='xpu2',device='xpu:2',kind=record['kind'],run_name=record['run_name'],
             workspace=workspace('xpu:2'),candidate_native_node_seconds=0.001,
             cross_card=None,reference=None,reference_released=released)
    if eager:
        wave=record['tensors']['waveform']
        row['cross_card']=dict(equal=True,device='xpu:2',reference_device='xpu:3',
            mode='native-eager-uncached',sample_rate=record['sample_rate'],
            shape=wave['shape'],dtype=wave['dtype'],waveform_sha256=wave['sha256'],reference_waveform_sha256=wave['sha256'])
        row['reference']=dict(workspace=workspace('xpu:3',364666868),released=dict(released),
            seconds={key:0.001 for key in ('reference_weight_and_latent_copy','reference_decode',
                     'reference_output_copy','reference_unload','reference_total')})
    record['audio_residency_evidence']=row


def make_decode_record(job, t):""")
source = source.replace('    sr.validate_decode_record(rec)', '    audio_evidence132(rec)\n    sr.validate_decode_record(rec)')
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
