#!/usr/bin/env python3
"""CPU fake123: synthetic residency and preview errors, never numerical evidence."""
from pathlib import Path

source = Path(__file__).with_name('fake_comfy122.py').read_text()
source = source[:source.rindex('exec(compile(source,')]
source = source.replace("'assert c.PACKET == 122'", "'assert c.PACKET == 123'")
exec(compile(source, str(Path(__file__).with_name('fake_comfy122.py')), 'exec'))
source = source.replace('choices=(49, 97, 121, 145)', 'choices=(49, 97, 121, 145, 169)')
source = source.replace("'chunk_145': True,", "'chunk_145': True, 'chunk_169': True, 'atomic_preview': True,")
source = source.replace("ap.add_argument('--display-device'", """ap.add_argument('--reference-hashes', type=Path)
ap.add_argument('--aux-residency', choices=('legacy', 'xpu2'), default='legacy')
ap.add_argument('--preview-route-error', choices=('none', 'healthy', 'fault', 'unavailable'), default='none')
ap.add_argument('--display-device'""")
source = source.replace("QID = c.qualification_id(a.frames, a.placement, a.anchor, a.decoder_graph, *LEVERS)", """QID = c.qualification_id(a.frames, a.placement, a.anchor, a.decoder_graph, *LEVERS)
SERVER_OPTIONS.update(aux_residency=a.aux_residency,
                      residency_qualification_id=c.residency_qualification_id(QID, a.aux_residency))""")
source = source.replace("PLAN = '0ef91a395112bd7d1ffecbbc2d74bf5ccc89267751447be9b21a4b4ec107c060'",
                        "PLAN = json.loads((a.contract_dir.parent / 'stream-plan.json').read_text())['plan_sha256']")
source = source.replace('(4 * 2**30 * (((a.frames - 1) // 8 + 1) ** 2) + 255) // 256', 'c.display_transient_bytes(a.frames)')
source = source.replace("'display_replica': replica_record(job, images['images']['sha256']),",
                        "'aux_residency': a.aux_residency, 'audio_device': 'xpu:2' if a.aux_residency == 'xpu2' else 'xpu:3', 'display_replica': replica_record(job, images['images']['sha256']),")
source = source.replace('def make_decode_record(job, t):', """def fake_aux_workspace(owner):
    if a.aux_residency != 'xpu2':
        return None
    from residency123 import check_aux_free
    return {label: dict(check_aux_free(16 * 2**30, before), owner=owner, device='xpu:2', mode='xpu2')
            for label, before in (('before', True), ('after', False))}


def fake_aux_memory(anchored):
    free = {'xpu:%d' % i: 16 * 2**30 for i in range(4)}
    return {'before': {'free': dict(free)}, 'after': {'free': dict(free)},
            'conditioning': [{'stage': stage, 'free_before': dict(free), 'free_after': dict(free)}
                             for stage in (('A', 'B') if anchored else ())]}


def make_decode_record(job, t):""")
source = source.replace("'aux_residency': a.aux_residency, 'audio_device':",
                        "'aux_audio_workspace': fake_aux_workspace('audio'), 'aux_residency': a.aux_residency, 'audio_device':")
source = source.replace("'memory': {}, 'storage':",
                        "'aux_upsampler_workspace': fake_aux_workspace('upsampler'), 'memory': fake_aux_memory(anchored), 'storage':")
source = source.replace('references=None, levers=LEVERS,', "references=json.loads(a.reference_hashes.read_text()) if a.reference_hashes else None, levers=LEVERS,")
source = source.replace("S = {'phase':", "PREVIEW_ERROR_SEEN = [False]\nS = {'phase':")
source = source.replace("if self.path.startswith('/ltx-stream/preview/'):\n            return", """if self.path.startswith('/ltx-stream/preview/'):
            if '/stream123-s' in self.path and a.preview_route_error != 'none':
                PREVIEW_ERROR_SEEN[0] = True
                return self.send(500, {'error': 'file changed during read'})
            return""")
source = source.replace("STATS['status_gets'] += 1", """STATS['status_gets'] += 1
            if PREVIEW_ERROR_SEEN[0] and a.preview_route_error == 'unavailable':
                return self.send(503, {'error': 'status unavailable'})
            if PREVIEW_ERROR_SEEN[0] and a.preview_route_error == 'fault':
                body = status()
                body.update(halted='injected fault after preview failure', fault={'message': 'injected'})
                return self.send(200, body)""")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
