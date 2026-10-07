"""Source/graph-only controls; no provider registration, tensors or execution."""
import copy
import os
from pathlib import Path
import tempfile
import unittest

import anchor as A
import graph as G


def binding_for(module):
    context=G.predecessor_context(module)
    return {'schema':'ltx.continuation111.anchor.v1','context':context,
        'capture_path':'/cpu/validation/'+context['capture_name']+'/tensors.safetensors',
        'capture_sha256':'b'*64,'anchor_sha256':'c'*64,'frame_index':48,
        'shape':[1,384,640,3],'dtype':'F32','byte_order':'little','byte_length':2949120,
        'source_file_identity':[1,2,146165448,4,5,1], 'header_sha256':'d'*64,
        'whole_capture_hash_verified':True, 'anchor_finite_verified':True,
        'other_tensor_finiteness_verified':False, 'transformation':'none'}


class Tests(unittest.TestCase):
    def chain(self,p=0):
        rows=[]
        for c in range(3):
            prior=rows[-1] if rows else None
            rows.append(G.build_chunk(p,c,'a'*64,predecessor=prior,
                                      binding=binding_for(prior) if prior else None))
        return rows

    def test_sealed110_basis_and_actual_native_conditioning_api(self):
        base,sources=G.basis()
        self.assertEqual(A.sha(G.canonical(base)),G.BASE_GRAPH_SHA)
        self.assertEqual(sources['source/comfy_extras/nodes_lt.py'],
                         '09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243')
        self.assertEqual(base['420']['class_type'],'LTXHostEmbeddingComponents')
        self.assertEqual(base['425']['inputs']['mode'],'graph-shard')
        self.assertEqual(base['364']['inputs']['mode'],'pipeline-window')
        self.assertEqual(base['356']['inputs'],{'width':320,'height':192,'length':49,'batch_size':1})
        with self.assertRaisesRegex(ValueError,'source changed'):
            G._read(G.PACKET/'manifest.json','f'*64)

    def test_source_reader_rejects_fifo_and_symlink_without_import_or_block(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError,'Nonregular'):G._read(fifo,'f'*64)
            link=root/'link';link.symlink_to(G.PACKET/'manifest.json')
            with self.assertRaisesRegex(ValueError,'Unsafe'):G._read(link,G.MANIFEST_SHA)

    def test_chunk0_is_ordinary_native_with_only_labels_seed_and_authority_rebinding(self):
        base,_=G.basis();out=G.build_chunk(0,0,'a'*64)
        graph=out['graph'];self.assertEqual(set(graph),set(base))
        for key in base:
            expected=copy.deepcopy(base[key])
            if 'run_name' in expected['inputs']:expected['inputs']['run_name']=out['chunk']['name']
            if key=='364':
                expected['inputs']['clip_index']=99911000
                expected['inputs']['qualification_id']=out['prototype_plan_sha256']
            self.assertEqual(graph[key],expected,key)
        self.assertIsNone(out['external_image_input'])
        self.assertIsNone(out['anchor_binding'])
        self.assertFalse(out['ready_for_submission'])

    def test_both_stage_anchors_follow_exact_native_edges_and_preserve_audio_sampling(self):
        base,_=G.basis();rows=self.chain()
        for row in rows[1:]:
            graph=row['graph']
            self.assertEqual(graph['377']['inputs']['video_latent'],['anchor_stage_a',0])
            self.assertEqual(graph['340']['inputs']['video_latent'],['anchor_stage_b',0])
            for name,edge in [('anchor_stage_a',['356',0]),('anchor_stage_b',['348',0])]:
                self.assertEqual(graph[name],{'class_type':'LTXVImgToVideoInplace','inputs':{
                    'vae':['420',2],'image':G.ANCHOR_EDGE,'latent':edge,'strength':1.0,'bypass':False}})
            for key in ('344','368','348','365','366','367','369','374','358','388','391','395','404','341','352'):
                self.assertEqual(graph[key],base[key],key)
            self.assertEqual(graph['338']['inputs']['noise_seed'],G.SEEDS[row['chunk']['index']])
            self.assertEqual(graph['339']['inputs']['noise_seed'],G.SEEDS[row['chunk']['index']])
            self.assertFalse(row['provider_registered']);self.assertFalse(row['runtime_admitted'])
            G.validate_module(row)

    def test_three_chunk_full_replay_has145_new_frames_per_pass_no_audio_policy(self):
        design=G.design()
        self.assertEqual(design['execution_order'],[(0,0),(0,1),(0,2),(1,0),(1,1),(1,2)])
        self.assertEqual(design['unique_video_frames_per_chain'],145)
        self.assertEqual(design['six_full_capture_bound_bytes'],877383216)
        first,repeat=self.chain(0),self.chain(1)
        self.assertEqual([r['chunk']['seed'] for r in first],[r['chunk']['seed'] for r in repeat])
        self.assertEqual([r['chunk']['new_video_frames'] for r in repeat],[49,48,48])
        self.assertEqual(len({r['chunk']['name'] for r in first+repeat}),6)
        self.assertTrue(all('unresolved' in r['audio'] for r in first+repeat))
        self.assertFalse(design['output_slicing_implemented'])

    def test_missing_wrong_pass_chunk_runtime_anchor_context_and_cycle_refused(self):
        first=self.chain()[0]
        with self.assertRaisesRegex(ValueError,'Missing predecessor'):G.build_chunk(0,1,'a'*64)
        with self.assertRaisesRegex(ValueError,'Chunk0'):G.build_chunk(0,0,'a'*64,predecessor=first)
        for mutate in ('pass','index','runtime','hash','context','shape'):
            prior=copy.deepcopy(first);binding=binding_for(prior)
            if mutate=='pass':prior['chunk']['pass_index']=1
            if mutate=='index':prior['chunk']['index']=1
            if mutate=='runtime':prior['target_runtime_manifest_sha256']='f'*64
            if mutate=='hash':prior['graph_sha256']='f'*64
            if mutate=='context':binding['context']['graph_sha256']='f'*64
            if mutate=='shape':binding['shape']=[1,256,256,3]
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                G.build_chunk(0,1,'a'*64,predecessor=prior,binding=binding)
        prior=copy.deepcopy(first);prior['chunk']['index']=1;prior['predecessor']=prior
        with self.assertRaisesRegex(ValueError,'order/runtime'):
            G.build_chunk(0,1,'a'*64,predecessor=prior,binding=binding_for(first))

    def test_mutated_conditioning_single_stage_arithmetic_or_registration_refused(self):
        row=self.chain()[1]
        for change in ('only-a','strength','bypass','bad-edge','seed','sigma','prompt','audio','ready'):
            value=copy.deepcopy(row);g=value['graph']
            if change=='only-a':g['340']['inputs']['video_latent']=['348',0]
            if change=='strength':g['anchor_stage_b']['inputs']['strength']=0.5
            if change=='bypass':g['anchor_stage_a']['inputs']['bypass']=True
            if change=='bad-edge':g['anchor_stage_a']['inputs']['image']=['missing',0]
            if change=='seed':g['338']['inputs']['noise_seed']+=1
            if change=='sigma':g['395']['inputs']['sigmas']='1,0'
            if change=='prompt':g['364']['inputs']['text']='another scene'
            if change=='audio':g['366']['inputs']['frames_number']=25
            if change=='ready':value['ready_for_submission']=True
            value['graph_sha256']=A.sha(G.canonical(g))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'module changed'):
                G.validate_module(value)


if __name__=='__main__':unittest.main()
