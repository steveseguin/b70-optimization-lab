#!/usr/bin/env python3
"""Exact sealed-117 successor assembly for packet118b. Default inventories; --build is explicit.

Installed in the packet as launch/encoder_runtime_common.py. Packet118b is the sealed packet117 with three
launch-selectable server-side levers. Walk selects the 117 inspector; timing still adds CPU overhead: the timing split (always on, measurement only), the four-card safety snapshot from residence
fingerprints (LTX_SNAPSHOT_MODE=walk|fingerprint, new snapshot_fingerprint.py, dual-checked against the walk in
qualification and on every 20th / near-floor stream chunk; latch snapshot-118-refused.json), and the decoder-graph
pool cap (LTX_DECODER_GRAPH_POOL_CAP_GB, optional, needs LTX_DECODER_GRAPH=1); `stream118b-` names, packet id
118, run names with `-sm<walk|fp>-`. Changed: integration.py, session.py, plan.py, stream_contract.py,
stream_receipts.py, qualification_gate.py, stream_decoder_graph.py, stream_anchor_decode.py and precompute_guard.py
(identity strings only), qualify_client.py, the new module, the geometry/capture-guard literals (the plan, the
qualification ids, the comparison mode, the prewrite schema) and the launcher literals that name the packet.
Every other file is copied byte-for-byte from 117 (itself verified against 116b, 116, 115, 114, 113, 112 and 111
at load and at launch). This builder never contacts an endpoint, imports Torch or touches a device. Changed parent
files survive under provenance/packet117/.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-continuation-stream-117'
PARENT_SHA = '5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9'
PACKET = ROOT / 'prepared-continuation-stream-118b'
FRAMES = ('49', '97', '121')
PLACEMENTS = ('two-way', 'two-way20-28')
ANCHORS = ('mixed', 'latent', 'frame', 'guide')
DECODER_GRAPH = ('0', '1')
ANCHOR_DECODE = ('full', 'cone')
BENCODE_OVERLAP = ('0', '1')
PREP_AHEAD = ('0', '1')
SNAPSHOT_MODES = {'walk': 'walk', 'fingerprint': 'fp'}     # LTX_SNAPSHOT_MODE -> run-name token (-sm<token>-)
LEVER_KEYS = [(f, p, a, d, ad, bo, pa) for f in FRAMES for p in PLACEMENTS for a in ANCHORS for d in DECODER_GRAPH
              for ad in ANCHOR_DECODE for bo in BENCODE_OVERLAP for pa in PREP_AHEAD
              if a == 'frame' or (ad, bo, pa) == ('full', '0', '0')]
RUN_NAMES = {'%s/%s/%s/dg%s/ad-%s/bo%s/pa%s/sm-%s' % (k + (m,)):
             'encoder-server-continuation-stream-118b-%s-dg%s-ad%s-bo%s-pa%s-sm%s-%s-w1-b1-p1-dxpu2-s256x256-f%s'
             % (k[2], k[3], k[4], k[5], k[6], token, k[1], k[0])
             for k in LEVER_KEYS for m, token in SNAPSHOT_MODES.items()}
AUTHOR = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261009-continuation118b-stream')
REFERENCE_SOURCE = 'reference-frame-qualification-hashes.json'
REFERENCE_PATH = 'resolution/reference-frame-hashes.json'
DECODER_GRAPH_LATCH = 'decoder-graph-116-refused.json'   # = stream_decoder_graph.LATCH_NAME (shared with 116/116b)
ANCHOR_DECODE_LATCH = 'anchor-decode-118-refused.json'   # = stream_anchor_decode.LATCH_NAME
PRECOMPUTE_LATCH = 'precompute-118-refused.json'          # = precompute_guard.LATCH_NAME
SNAPSHOT_LATCH = 'snapshot-118-refused.json'              # = snapshot_fingerprint.LATCH_NAME
# Packet118b runs packet 117's cone and precompute code unchanged: a packet-117 latch refuses the lever too.
ANCHOR_DECODE_LATCHES = ('anchor-decode-117-refused.json', ANCHOR_DECODE_LATCH)
PRECOMPUTE_LATCHES = ('precompute-117-refused.json', PRECOMPUTE_LATCH)
PLAN = AUTHOR / 'stream-plan.json'
PLAN_SHA = 'd36c188d695c36b2a8849da687d7fe004859888d22af606d94e2ec48afa47b30'
PARENT_PLAN_SHA = '8390d15e01a7107948484ea76f90b2661a31a68a42e1b2a72fb803835e55d4c4'
PARENT_QIDS = {
    '121/two-way/frame/dg0/ad-cone/bo0/pa0': 'babae9a3e445287d1a1c556c88c0f445a11fe3b7c32955129b6f10bc929460b8',
    '121/two-way/frame/dg0/ad-cone/bo0/pa1': 'a75587ef1fafe922dff523d317c02a7c8bacd03388b2a52ef134d9ef5f8b50dc',
    '121/two-way/frame/dg0/ad-cone/bo1/pa0': '36f23a012f3687f2bf9db4e836ea8a7c01ab617ab18abba7867f1a179da0f6c7',
    '121/two-way/frame/dg0/ad-cone/bo1/pa1': 'd38a0a21aeca0d7b0e133304275e1f1668c52b39493e49f33bc6f2a1f553616d',
    '121/two-way/frame/dg0/ad-full/bo0/pa0': 'a5f4768e42e3947d9a23ba3697fe520b3e6bbb8147e2d5b2619d0bafbad91b9d',
    '121/two-way/frame/dg0/ad-full/bo0/pa1': '27a670284bae30913f6c4e0dfd79f8fecfbaacbba2a19379ed93aa7ba2fc6159',
    '121/two-way/frame/dg0/ad-full/bo1/pa0': 'a63bada04cd5a41f6f7c0ad6bbd53239f2e9b7ddf2f81a590e9a8d17a1355436',
    '121/two-way/frame/dg0/ad-full/bo1/pa1': 'c6506268fa1048fa7c29f70a6a76b3273395ea11352fb0875b8d0a504c36ba9a',
    '121/two-way/frame/dg1/ad-cone/bo0/pa0': '78aab30d8c366f04945b1a878f63f05cb6c91feec526d2559e5b72c62701412b',
    '121/two-way/frame/dg1/ad-cone/bo0/pa1': '5a375bb43669157d1107d9dd9bea822bb18328a641465c682933685b9dbb73c8',
    '121/two-way/frame/dg1/ad-cone/bo1/pa0': 'd08197eed4e88cb5c5fcf703248e9b8bca3c9085bfc9a6848f80d8cbedeb669e',
    '121/two-way/frame/dg1/ad-cone/bo1/pa1': '2dfb8369532e2af1d03603cc7c8201542e68e4fe8d84f475483ab29dad9e69fb',
    '121/two-way/frame/dg1/ad-full/bo0/pa0': 'f09ab6c0467e79c6281a2184155cd706eb6be68fdc6cd5fffac6f6a406536ae7',
    '121/two-way/frame/dg1/ad-full/bo0/pa1': 'a1f571dbf67f3419685d104e030a5d108734a46df5a06e43a38e515bc2d07077',
    '121/two-way/frame/dg1/ad-full/bo1/pa0': 'f9a828d328cdb95f1f4645c88e2cf8c3ca1bbcaaf7b2e68dfb3252c51d467eec',
    '121/two-way/frame/dg1/ad-full/bo1/pa1': '75a1362f752764e050618b0b422215d06c8ed09f0a74dd68257a5fcfe33d5cf6',
    '121/two-way/guide/dg0/ad-full/bo0/pa0': '64b456344703ac5bc6948652fe42a0e04c46acd828d56241760baf0c5764a6fe',
    '121/two-way/guide/dg1/ad-full/bo0/pa0': 'ae3e5e3433b5af564d06311d09fa017b60286bd997f85f8910906dc0e739a239',
    '121/two-way/latent/dg0/ad-full/bo0/pa0': '8d68c6e1bebca0f86bcd7487e231ec5aed3d6b2ef03be9c84f638f23a0948766',
    '121/two-way/latent/dg1/ad-full/bo0/pa0': '1341338c64244a45ca52c3d0f1a3c859e9331ea19dba5bca01bceda743518c8b',
    '121/two-way/mixed/dg0/ad-full/bo0/pa0': '76715c45568eeba161c575ebb86ac3a4d5556ac50834fc2e0404b9a37fcadb34',
    '121/two-way/mixed/dg1/ad-full/bo0/pa0': '4a4205fc8c272f2c9c7a2adc8aa71874348f17019650ee7e5c9c16493c2276d2',
    '121/two-way20-28/frame/dg0/ad-cone/bo0/pa0': 'ea0d62b41efa53dc75ed23e823ce57375c7cbdf153a4cbc935caeda9d7051e3b',
    '121/two-way20-28/frame/dg0/ad-cone/bo0/pa1': '25e767c48ddfd4d46385d9216a5573ce8c738ee541e9ee812534cab71d10c834',
    '121/two-way20-28/frame/dg0/ad-cone/bo1/pa0': '909000a2c994788f074283e2af6c3cc1c3116e0533f0f21ef41078931ec97545',
    '121/two-way20-28/frame/dg0/ad-cone/bo1/pa1': '7b5244e746214f4fcf03bdb7366b1dcd3ca5aaf5dd4cb4b6c4ff6339cd32667a',
    '121/two-way20-28/frame/dg0/ad-full/bo0/pa0': '77886bf82f8968045a85daa25babe88e9d1b05a05fe9924134460bc9ba920e22',
    '121/two-way20-28/frame/dg0/ad-full/bo0/pa1': '1f98d88009fc06a57daecab2b806dd4563359d9784bd60e374e974df12b6d2bb',
    '121/two-way20-28/frame/dg0/ad-full/bo1/pa0': '11b84789692d817b2e041d20c50dc6bd6733f9a88db0587810f6d3c0faf9c0a6',
    '121/two-way20-28/frame/dg0/ad-full/bo1/pa1': '508fe5004191c058e324243c1b9fdefde4e6b47c2d62f67e493aaca1307d0a02',
    '121/two-way20-28/frame/dg1/ad-cone/bo0/pa0': '48801bdd3fdd533bd5778bd88b3c81f479641911e4e4ea96eb356a3d81c1aa0d',
    '121/two-way20-28/frame/dg1/ad-cone/bo0/pa1': '1d2325d6e93a5abceb8a7580310162d153e34c16d2e3ea73a8de0be8765a8538',
    '121/two-way20-28/frame/dg1/ad-cone/bo1/pa0': '7099f8cce9aa685dfb3a3a69d215181d8e8bcc8bc32b4b8c11273ca94a3e2027',
    '121/two-way20-28/frame/dg1/ad-cone/bo1/pa1': 'cf27a212158c3b9bc2d4989c277180522307d7b573b76aba0db9c844b935d222',
    '121/two-way20-28/frame/dg1/ad-full/bo0/pa0': '6ca305a516bb6234c1351c005070f42acd383af0919fd8168b698d4bc9462316',
    '121/two-way20-28/frame/dg1/ad-full/bo0/pa1': '52d22b4301e5d7ee9a4e6be5741a9ea48c6af77300f52f7a4d29a870e50b9a15',
    '121/two-way20-28/frame/dg1/ad-full/bo1/pa0': '9b67a5b9c144b89e264874a9747ff4effbefbd01326a6080e721e98bbe184fd6',
    '121/two-way20-28/frame/dg1/ad-full/bo1/pa1': 'a1f082626c1b8cc6627999a8f1a229e132e396bbba37b047c78286bb4e44b47b',
    '121/two-way20-28/guide/dg0/ad-full/bo0/pa0': '6926cbdd0fd2640bd8c5884ce207e4bfd7aca9f0abdc4c200002f6e579ce9ddb',
    '121/two-way20-28/guide/dg1/ad-full/bo0/pa0': 'f2ae8abafcab32a04eaf4b9532b0e8a83693d3dc6c8cd8d875c6263533716370',
    '121/two-way20-28/latent/dg0/ad-full/bo0/pa0': '8ef1044327d8ee1f4083fa4a9c9b47e81193367d089d84e3a46a9fab09364373',
    '121/two-way20-28/latent/dg1/ad-full/bo0/pa0': '49322e0c7275ff8acf0255d3a742e32dc07d9f6a49fcb0dd362329a1e2c37add',
    '121/two-way20-28/mixed/dg0/ad-full/bo0/pa0': 'b340aaefd42e31dc5fff8711dba3c8bee897ade9494e8d7c0578f92dbd014955',
    '121/two-way20-28/mixed/dg1/ad-full/bo0/pa0': '3c574dccce431ef14e6cae7c81f020a098e4941c9a4931c5a9fae292aaefbb6d',
    '49/two-way/frame/dg0/ad-cone/bo0/pa0': '472db89a61f87442427ca6dd8c4195fedeca6ae1bb1fae066d1fc04ea5f85568',
    '49/two-way/frame/dg0/ad-cone/bo0/pa1': 'ab3adbb6311950013c9228d3550847f07379208a7b58516d47592fdc4b48f01c',
    '49/two-way/frame/dg0/ad-cone/bo1/pa0': '2f6d8e88e31bb6354f23d82da796e68bd5df071674bb6cb16ec9e69c13d299d4',
    '49/two-way/frame/dg0/ad-cone/bo1/pa1': 'aa592a5476cb37ff38f9fdac3b7f872b1c1ec61a3bc36d6e0ff0d1347d39ef05',
    '49/two-way/frame/dg0/ad-full/bo0/pa0': '37931488480302023dac4d4cf13b049cdf78ed74333ffa63c77a8f6c04e4826a',
    '49/two-way/frame/dg0/ad-full/bo0/pa1': 'c2a1e6480665c70bdb93c81b54df890941032d770b9fd54f6f836d2ee74f8c6c',
    '49/two-way/frame/dg0/ad-full/bo1/pa0': '00f8442766a320dbdba8da79bd24b8b0efc8c74d2e4080c3448295fdd51158f6',
    '49/two-way/frame/dg0/ad-full/bo1/pa1': '98af577057f3db8cf33b546470a1acf908942d2d3e2f24ce8b58ae71a1660c2d',
    '49/two-way/frame/dg1/ad-cone/bo0/pa0': '903fd87cee2c003a48033e63b570e18c0da276b1461c75631e336f8af1e720f2',
    '49/two-way/frame/dg1/ad-cone/bo0/pa1': '7848f93aaeeaeb2e2661f0db96223ca7a3239ff21429dc1368c8c545865a601b',
    '49/two-way/frame/dg1/ad-cone/bo1/pa0': 'faeda557ee65ce411c4680508983e064583eb64e37a339a18cbc317115fac59f',
    '49/two-way/frame/dg1/ad-cone/bo1/pa1': '25476a3f7dd38245c485665772dda46869d51c1ae1ba472cfddc874a68f2f953',
    '49/two-way/frame/dg1/ad-full/bo0/pa0': '9c5ca70f08e548a8ad160487cb0a5aae7e33591f1a1adfb9ff739d6f90aecc6b',
    '49/two-way/frame/dg1/ad-full/bo0/pa1': '1e38fdebb57cc4404d44be2b6ec595d8de2de12b90f9467728de1141d24297ec',
    '49/two-way/frame/dg1/ad-full/bo1/pa0': '2f496d551f725cd97ac39961a144f24633bbd8cf9e066388a9db81f855bd57f1',
    '49/two-way/frame/dg1/ad-full/bo1/pa1': '25de76c0e02213611477c9897a44c8060659a7ebb66b4e61e875c8229da188dd',
    '49/two-way/guide/dg0/ad-full/bo0/pa0': '8f3f65a0a4ae41b8abf704ea4a2de8f5cbbfa53070ea9a3382030ab42b8ba577',
    '49/two-way/guide/dg1/ad-full/bo0/pa0': '38adf4b097a84c9919c02d7e04991a8cd84a345615d4547e11e0b664ad7b6af0',
    '49/two-way/latent/dg0/ad-full/bo0/pa0': 'ccdedbf465460e72cefc2568b02abd4ed1044d834f3996fcf4ec44c8d748cf66',
    '49/two-way/latent/dg1/ad-full/bo0/pa0': 'f320c39aa901fb26fb0734a91d98a42d708497c0668401bccd82f9e4dc1d2721',
    '49/two-way/mixed/dg0/ad-full/bo0/pa0': '7256cae7944ae497c9b6e128d30f22ee16cbc7fd2020ef4104e54cf8108acbac',
    '49/two-way/mixed/dg1/ad-full/bo0/pa0': '3684efb97a181927b836914af6f1d56f9293f4761075c5e5f9232038c71505ef',
    '49/two-way20-28/frame/dg0/ad-cone/bo0/pa0': 'db0770aca5762fb84736a8a9d80ae36f8dcb83ae0c9d0d5bebf07c01c2bfe7fe',
    '49/two-way20-28/frame/dg0/ad-cone/bo0/pa1': 'cb8de51cd014e5db3a2612214fe5aed6129328b545140653a7e1fa399152ba8d',
    '49/two-way20-28/frame/dg0/ad-cone/bo1/pa0': 'a4f351f14c2db2ddcd24932384b8587a4e70e7dcca0ed0d1b2196d9d460e559f',
    '49/two-way20-28/frame/dg0/ad-cone/bo1/pa1': '67aea773db5607b1e8a5bb0b12931e027edd869508ffa341870248ecff798867',
    '49/two-way20-28/frame/dg0/ad-full/bo0/pa0': 'a7d1d836f2b2c9a1f3c36bed7427186cf8e4d36baacc7a2859d0443953d53110',
    '49/two-way20-28/frame/dg0/ad-full/bo0/pa1': '57e642da5dd6951963288283b6c6fbc82165f272d083bc9dd57f20802cddd32f',
    '49/two-way20-28/frame/dg0/ad-full/bo1/pa0': 'a8b3994ed4eb3922fe471a9d63cb881ace195b4f433c96f62fd9d36976cdfc73',
    '49/two-way20-28/frame/dg0/ad-full/bo1/pa1': 'cf3e5a74018f2648636848958cb815fe7668418d2b03086682fc103edf4ef2a8',
    '49/two-way20-28/frame/dg1/ad-cone/bo0/pa0': 'f22bcd39e4002442c5649645c1025de3881497e8ba65ff846ed22198dbbd5734',
    '49/two-way20-28/frame/dg1/ad-cone/bo0/pa1': '11aa162d4a41331c0d08f4cc9348779983051184e6b2f5a08d1626ed8affa12d',
    '49/two-way20-28/frame/dg1/ad-cone/bo1/pa0': '667d4f6b1131d82e94cb41d3c8da28284edfa880c1224afb0a480adbb551f560',
    '49/two-way20-28/frame/dg1/ad-cone/bo1/pa1': 'e5a49a6526b4cacc96ec3f39babc02e6603cf748cf00a09c84634a63c98c9bcb',
    '49/two-way20-28/frame/dg1/ad-full/bo0/pa0': '68ded339cbd02716842c10d446b7b98678d8eb487c0bc8dfca9cddce90d50fb9',
    '49/two-way20-28/frame/dg1/ad-full/bo0/pa1': '7103868f01c7acc56b1c0fc74ae334bfd75f59fbd220272d7b00a25d9fa47d13',
    '49/two-way20-28/frame/dg1/ad-full/bo1/pa0': '101358dd46ad74e57a9112d3ad42b4389dde517b9924b217bd498c3ed00293e9',
    '49/two-way20-28/frame/dg1/ad-full/bo1/pa1': '043ed124cad31550c5760e3dcffe34126e47aba291e69acc4a3818daa664a6b8',
    '49/two-way20-28/guide/dg0/ad-full/bo0/pa0': 'b8b637f602b2f14695b80875f700c839d80198dfe2a20fc235d42f2fc28cb36b',
    '49/two-way20-28/guide/dg1/ad-full/bo0/pa0': '95d9329a84e4af9e6b24a2d976bfb4d936d896717f0af505a466dbd23fd1b67e',
    '49/two-way20-28/latent/dg0/ad-full/bo0/pa0': '448dc7495d26159930a034922d8896410dcd03bf6f8533ebb94f04d1b12c30ec',
    '49/two-way20-28/latent/dg1/ad-full/bo0/pa0': '00c70bf2908dec4ff9f4fa4aad48d76787cde011c69b5ec34db9e5f46250ae40',
    '49/two-way20-28/mixed/dg0/ad-full/bo0/pa0': 'b659a37d0115fd41ab0c0fd00df518695e2d2529971fed158b0ad0d3b55d0c8b',
    '49/two-way20-28/mixed/dg1/ad-full/bo0/pa0': '982045e30fb3ea951effa65c089e50e796c8137f7cfb2d41c118c0424f3a6df1',
    '97/two-way/frame/dg0/ad-cone/bo0/pa0': '7565d4651c593ee106d809dc146017c5d5338640a058463825f32744762e1314',
    '97/two-way/frame/dg0/ad-cone/bo0/pa1': 'a1cd9224574e8a90a103b1663d36520e60e5116c83b6c02f9cbcf4a8f4f37fb7',
    '97/two-way/frame/dg0/ad-cone/bo1/pa0': '026db2440d14d4da967b71700840709b1c99a92c81850f38cfb956efb742096a',
    '97/two-way/frame/dg0/ad-cone/bo1/pa1': '81462a7a2751df310d7a95341a13d40ddc36d759cd60795f0a6942eb56a22920',
    '97/two-way/frame/dg0/ad-full/bo0/pa0': '517b43ccc924ba9f45284578d0aa5bf019b1738782d33d81505b30be8cdfb81c',
    '97/two-way/frame/dg0/ad-full/bo0/pa1': '1d1f720a2c7d5040ab7212e93576825bbae3f346a08f70e9b7aa15072a6b992a',
    '97/two-way/frame/dg0/ad-full/bo1/pa0': '4d27c9d27212be3eeaaf1362bedf1bbe690dd8e819d51b8425359574703ef529',
    '97/two-way/frame/dg0/ad-full/bo1/pa1': 'a8b82cca03b55fa6d5dfeaa7b35a307e5698cae6200cd9b33ffd8b5187f2ba13',
    '97/two-way/frame/dg1/ad-cone/bo0/pa0': '296850941481d06d2363247513404209abfae4e167a8baa01e0313861056c59f',
    '97/two-way/frame/dg1/ad-cone/bo0/pa1': 'a5609aa5593fa138af4c09c2b4305514e2d5f5832c5048c985c2fd902b2c4914',
    '97/two-way/frame/dg1/ad-cone/bo1/pa0': '4518fb83a1a5f9485b00e8b9c49a36489952b86388fe8266fc621c99f84eb721',
    '97/two-way/frame/dg1/ad-cone/bo1/pa1': '07b8e6d527e81e3f36404b3754a17d193073d761d21be45639f9a71c6431b16f',
    '97/two-way/frame/dg1/ad-full/bo0/pa0': '6c2430850f14cd9b52a6193c0be6121dd24344bad895783aeb7002fcef8a8ed7',
    '97/two-way/frame/dg1/ad-full/bo0/pa1': 'adafe82868f9a8da5badf46c4c8e3ec0a9792d9e034cdb85b0308d77dcda36dc',
    '97/two-way/frame/dg1/ad-full/bo1/pa0': '0964d0e0f80180647285633cda34eca4fdce1c51cbc782e30068c9744e3c1c21',
    '97/two-way/frame/dg1/ad-full/bo1/pa1': 'f25eec9a1a802ac9f5a662e0a70db5428cc121f6a48d36d435c2e1d2f30d4add',
    '97/two-way/guide/dg0/ad-full/bo0/pa0': '3611905b4f9c8e6e137c01302040bcba64b5ae9896ec74e37d04cd239f7d16b1',
    '97/two-way/guide/dg1/ad-full/bo0/pa0': '222e4af10ad6f4d66afe7ddcd8d5eb9a06800b651bf157ea78c930225f11ac6b',
    '97/two-way/latent/dg0/ad-full/bo0/pa0': '1fe3a34794a8522099364b4018f27d947239bedbaf512b047527e389f3da69b3',
    '97/two-way/latent/dg1/ad-full/bo0/pa0': '5476cd1b0d1b3fd12476006e6ebe6e886b145e6b3494d70a5c7aab71d0373ba9',
    '97/two-way/mixed/dg0/ad-full/bo0/pa0': 'b290e4f589c3ea62e037ef8ff64d87b31ad46db098bb04b30a72b0168176d7a4',
    '97/two-way/mixed/dg1/ad-full/bo0/pa0': 'c77e0f2dc472539eaa58972e3a524be727aa39223e7d7f0bed16e34d600870db',
    '97/two-way20-28/frame/dg0/ad-cone/bo0/pa0': '2ccd87631ad64ad41ae0b223e96f1be59ef719787a792cbf11be1c83084b88f3',
    '97/two-way20-28/frame/dg0/ad-cone/bo0/pa1': '093854463a4120d8338f8ef64363634344df47924d6ef3d94e760029ddd82f0f',
    '97/two-way20-28/frame/dg0/ad-cone/bo1/pa0': '2762c8e1f771a03da653a2882360ec38573f42e62a9fd90c96ad21c9fcd618b4',
    '97/two-way20-28/frame/dg0/ad-cone/bo1/pa1': '709c3f7543e0f6db0ef31567838cb8f6ab7d7170470a0eda449e907250445066',
    '97/two-way20-28/frame/dg0/ad-full/bo0/pa0': '538155b026f4399c8b8b1e9a860289876013913b61fd220e57ba833db11120ee',
    '97/two-way20-28/frame/dg0/ad-full/bo0/pa1': 'dbc3eda723ed3c5bc0302b84ffa3ea8f5ed80bce9366eeaba4e6686513c5a34e',
    '97/two-way20-28/frame/dg0/ad-full/bo1/pa0': 'eb58a6fad5a4c61caf57228b64743116a92484da0a579663245744a14b026489',
    '97/two-way20-28/frame/dg0/ad-full/bo1/pa1': '7432c74585efe9777ca242abf56d17f4c93c3e7ec4484135f31c5a5f56501bad',
    '97/two-way20-28/frame/dg1/ad-cone/bo0/pa0': '3f44e6284c3931b4ef843a32e3cba1d301675336995c3228aecf34ab2f180e69',
    '97/two-way20-28/frame/dg1/ad-cone/bo0/pa1': 'a567485ca63783ab7a0c31db19800d7cf6f1ff0027d21039214a241b17432db2',
    '97/two-way20-28/frame/dg1/ad-cone/bo1/pa0': '4184dfde03009c105e6621ddb648c3748ddc4b02997c939273ca2f689958211f',
    '97/two-way20-28/frame/dg1/ad-cone/bo1/pa1': '13e17b61cb157c8bf40373f12b26b0f3fe3482709e7b35994701f9c3092acb3e',
    '97/two-way20-28/frame/dg1/ad-full/bo0/pa0': 'dad2fd937d92470035fef2764339adecf9ba087627ad91816c7b5de1b07adff6',
    '97/two-way20-28/frame/dg1/ad-full/bo0/pa1': 'fa00e0c5c4773b635c78a9c38a8c26eb7aea95dc94dc67696533eef4b27334d6',
    '97/two-way20-28/frame/dg1/ad-full/bo1/pa0': 'b35d87809e588c80269ba5d39b4978aeba75e6113e8011a860a63429d2a87d97',
    '97/two-way20-28/frame/dg1/ad-full/bo1/pa1': 'fae1fdf7dda58017deffcff968cfc41b48d3300e2a91bbafa31c5a63d53c3f5b',
    '97/two-way20-28/guide/dg0/ad-full/bo0/pa0': '621f27bfb34dfc85e565390da945145ad66dec2ccd5d36c785ce8ce76f627fdb',
    '97/two-way20-28/guide/dg1/ad-full/bo0/pa0': '64e88b1ca61259d342b24171ee965f4940a39a6d4b1955bc2f4fa6d5f080b527',
    '97/two-way20-28/latent/dg0/ad-full/bo0/pa0': 'ed36da342c6ee54dbe51bda4363d6c2bb68124df309ac989bbeefe73239ce64b',
    '97/two-way20-28/latent/dg1/ad-full/bo0/pa0': 'd5d3f84c84ab5e58faccb2e5faa64f4829de06601821f0d7cc297669f5c30a79',
    '97/two-way20-28/mixed/dg0/ad-full/bo0/pa0': 'cb80f42e51a994fc3b5914a01338d37c146ee299cf6111b08b8bd2090c58c90f',
    '97/two-way20-28/mixed/dg1/ad-full/bo0/pa0': 'db6a5c2fb7afe22e86e971663bb0fe99f1c8851978ea376a3805b2f65b4d6103',
}
QIDS = {'121/two-way/frame/dg0/ad-cone/bo0/pa0': '618fa86cd694b50a427601030d3d97a937a1a936729b3a3432c22867293f282b',
 '121/two-way/frame/dg0/ad-cone/bo0/pa1': '43986e09b60c670a61a1cf24be35948daccbe1444b62ca0e2740cc9d7234d4b3',
 '121/two-way/frame/dg0/ad-cone/bo1/pa0': 'ffedc918238e758fb8109f1a47ecd9d4ee99459a4563ecaa4719ea4f0a886f9c',
 '121/two-way/frame/dg0/ad-cone/bo1/pa1': '8e97ba0c3a5e431161f9e8aa155dfcb1b140b0b44eba33c4cd722cb560604b29',
 '121/two-way/frame/dg0/ad-full/bo0/pa0': '750e3d24eacedeb1036dcabc99969a3793a51f19a01081b8a83bf2ad57840fd9',
 '121/two-way/frame/dg0/ad-full/bo0/pa1': 'fd20f7283b5cfd4a5fe8711245d283871d2270a4fd4a63853f68413402c5f222',
 '121/two-way/frame/dg0/ad-full/bo1/pa0': '34fe17161a78b40cf8ad6ef55d43512a866602bbd8e5aabc1d26f6bdabcc8ec7',
 '121/two-way/frame/dg0/ad-full/bo1/pa1': 'dfc55696f9abe34b18db0bb8afa1ad3628187df15d3c7b40d0f02c4472fdfd74',
 '121/two-way/frame/dg1/ad-cone/bo0/pa0': '2ae1253675338ba411260755e5f034b2dcf11ff9c2b123625d8d35c6d631290e',
 '121/two-way/frame/dg1/ad-cone/bo0/pa1': 'c6b3c72cc833930aea32e6bc0cba80bcf9d6c37c257f752f3affb7c9ad662867',
 '121/two-way/frame/dg1/ad-cone/bo1/pa0': 'e5f91330505d2a2bb1b62faa3f689459bbf33c37ddefd4b7d24debcb7d309b64',
 '121/two-way/frame/dg1/ad-cone/bo1/pa1': 'f3c6fa63f0b19284ca1ed969d752a552451b16e353523814876b8e6bccb0a7a3',
 '121/two-way/frame/dg1/ad-full/bo0/pa0': 'dcd6c8d28af710263968846626a75f7a98e8a4eaeb2673df35ef4df3078ab03d',
 '121/two-way/frame/dg1/ad-full/bo0/pa1': '9edf76c7614c8395512c9b11edb68f08207c8636eca271809cff7e93ab0a396c',
 '121/two-way/frame/dg1/ad-full/bo1/pa0': '6fa1e86e309bd44c00be6781d12c47cc8f55ca484472ca3d8dd010a2ed055905',
 '121/two-way/frame/dg1/ad-full/bo1/pa1': '38549776b9bfd09d3297d78be65555fe6cc6be17d8b02d0be0aab3b25e0198fd',
 '121/two-way/guide/dg0/ad-full/bo0/pa0': '8cd643d72c3695244f1844608b418f72a17bb6f1d54e7bf6969b421d8bcaafe8',
 '121/two-way/guide/dg1/ad-full/bo0/pa0': 'd638725a3e33aaeca7644c51acefedbb836a7fc63d94f0ed57ff2f0e0df2455b',
 '121/two-way/latent/dg0/ad-full/bo0/pa0': '5fd5863ceac424daab82ca3017e82d03dff83efaa28d1842fc75003972ae6806',
 '121/two-way/latent/dg1/ad-full/bo0/pa0': '67dfe8957514de64e58d8fd64f36ffa94be6f1ea5fd1982294b109571f6e796d',
 '121/two-way/mixed/dg0/ad-full/bo0/pa0': '342cbc6ba3e01ad23188b07f6afaa1cc21879a7e8d7b22194568ac9aee13d147',
 '121/two-way/mixed/dg1/ad-full/bo0/pa0': 'd061d60e920eb01cd450f19c9213c02dc0459300d98dab9e72a00f6776776ff6',
 '121/two-way20-28/frame/dg0/ad-cone/bo0/pa0': '3182db36377a2c8b1f78b242391831d504bc1f26a30f95aebba9d65cb2eb8d40',
 '121/two-way20-28/frame/dg0/ad-cone/bo0/pa1': '7ed1aace38ef123f3ff4ebbf9f6005ce8fc288c6daa0d2ef1a545295735e11c3',
 '121/two-way20-28/frame/dg0/ad-cone/bo1/pa0': '57a94d6117d34ba00162bbe19a57e96dc368380c1a9c8a3bbb3aedaeae86d16e',
 '121/two-way20-28/frame/dg0/ad-cone/bo1/pa1': '0b138ef0346650ef4bab33fd4979722cdb2e3ba46fb0bf688ff663e9e7925e10',
 '121/two-way20-28/frame/dg0/ad-full/bo0/pa0': '762316e380d6080db1c117c804ff219fce2ec19dd3e7f0cdab9031e73a44196e',
 '121/two-way20-28/frame/dg0/ad-full/bo0/pa1': '70a7e7dce2b442d7c89f02fcb61149336dfc9024448c2a31570f214d9c31de79',
 '121/two-way20-28/frame/dg0/ad-full/bo1/pa0': 'd768f62fc40e760094a382eb0aacd9eb027d84a25d7e1111370017e894a1f966',
 '121/two-way20-28/frame/dg0/ad-full/bo1/pa1': '42d15b733d18c8790d7357db59be779d3389fac7b39766ca9af35da2bfa21031',
 '121/two-way20-28/frame/dg1/ad-cone/bo0/pa0': '5da653474c39d57b0976b776f019f18151c46be85dcd2bfd0d3308cb656edb7b',
 '121/two-way20-28/frame/dg1/ad-cone/bo0/pa1': 'bfb441c5b09a7b1bd792c442934c8a9e08276dda01c3094c4e5b13e34eccefd9',
 '121/two-way20-28/frame/dg1/ad-cone/bo1/pa0': '02a9c747dcc1100e18d97d976f81f30e4aa093b8af1c245c3c3a9106e6c47615',
 '121/two-way20-28/frame/dg1/ad-cone/bo1/pa1': '2d54fb73865ca84b6e2536f1defe45083064a28c9e6c739acba2d69755ecc80a',
 '121/two-way20-28/frame/dg1/ad-full/bo0/pa0': '4549bb1bdc77456c8956b67d88c5439cd47de3a303c83d25d77604298404aaf9',
 '121/two-way20-28/frame/dg1/ad-full/bo0/pa1': '683c1a38267ffe91773db669536ba9d7e8f343a18be8c1e468ee2f2b73d59310',
 '121/two-way20-28/frame/dg1/ad-full/bo1/pa0': '0e09d0a7d1cde813525e0cb4689e1620c25f38da25a08311aa33328062e6e517',
 '121/two-way20-28/frame/dg1/ad-full/bo1/pa1': '5ff94ca6b593b21af716991566240670c64f3a5c67b58d0a8e18663d1e0d28ef',
 '121/two-way20-28/guide/dg0/ad-full/bo0/pa0': '69d93acf5aa99c700bfa6562f99e28fec7800a90ead88eac259ed8b4c0fdf228',
 '121/two-way20-28/guide/dg1/ad-full/bo0/pa0': '56418567390e17427636bc881f710e9430ac055ae90ed76ba47553b096200669',
 '121/two-way20-28/latent/dg0/ad-full/bo0/pa0': '566b03a3ff68903f9272406a0d1ac3e7f7f0f0de889f583e910bafc9129b6abe',
 '121/two-way20-28/latent/dg1/ad-full/bo0/pa0': '61bfd391ed75f136cd0d181750f358e06399d853d42c737715b78fe124013679',
 '121/two-way20-28/mixed/dg0/ad-full/bo0/pa0': 'e6653c64eacf9ae450332bef01fa3d9c7fbf91337ebb6f983dc9f2fbcf623d01',
 '121/two-way20-28/mixed/dg1/ad-full/bo0/pa0': '4e30f27ca470b3ee3b104aa3ef15db66b21b2b7f22358a3530c869634dee38ea',
 '49/two-way/frame/dg0/ad-cone/bo0/pa0': '04af58992cbb26edee01c09849012a469c34a666e4121565f9f32f8b05b47e29',
 '49/two-way/frame/dg0/ad-cone/bo0/pa1': '56d46b5eb03a2227540533fd78c50f53201a5a047d5fdec46df94eb35f49f079',
 '49/two-way/frame/dg0/ad-cone/bo1/pa0': '3381fdcaaecce38707b297d4c10d5b6c6da6757693469c64f28c0f9d5338ac77',
 '49/two-way/frame/dg0/ad-cone/bo1/pa1': '8546a15edd98787222645a6c9231714b97647a33137851a7b2f244fc3938ef77',
 '49/two-way/frame/dg0/ad-full/bo0/pa0': 'bbcca11df814043f4fa42d70fc7649d510cb7f5f2951e808ba7ac29f86bcd729',
 '49/two-way/frame/dg0/ad-full/bo0/pa1': 'a0d73c964be0c6830aa42567d544f419ad95b7d4499b271373b13886bd5e2d78',
 '49/two-way/frame/dg0/ad-full/bo1/pa0': 'b372277f798ad94d956478745c5ff8b115b35d03dc8011ac75db0d7a0bafd09e',
 '49/two-way/frame/dg0/ad-full/bo1/pa1': '147b83e41855c1651420717c6bbd9bc477b3609a6785950b64a7b55706683af8',
 '49/two-way/frame/dg1/ad-cone/bo0/pa0': '6835139f7b31f687503f7ad375b59f600d7cf6cff47d5663a8ded64330f90b42',
 '49/two-way/frame/dg1/ad-cone/bo0/pa1': '4c68b865a2f1c9afa9c7c72bdab7ea48a2c10544dfedb09c0536fccf5a13667c',
 '49/two-way/frame/dg1/ad-cone/bo1/pa0': 'ece459657d2b42dd96ba4cd8e83f1872e4564753221643454be3e5d5b918142d',
 '49/two-way/frame/dg1/ad-cone/bo1/pa1': '0f69c88323ed4ea18a47e92b36a7c146dabbd48a33fc48ed4689af67ce238a66',
 '49/two-way/frame/dg1/ad-full/bo0/pa0': 'c872675971acf8edc979d20a359bec54cd6de73095de46463b80dcb214cbe365',
 '49/two-way/frame/dg1/ad-full/bo0/pa1': '2c97ca364fdc64a0a055bf4544e1cf5485033b897f299f3f37d06bdd8838539e',
 '49/two-way/frame/dg1/ad-full/bo1/pa0': '81834fa93ed8a785e3bbd27dca9144349d67fad3a27d65a0d0560817e5b6057f',
 '49/two-way/frame/dg1/ad-full/bo1/pa1': 'ee2ce609cca36ee712fc17c009f4828a240d1c54dface95c3a8afab82f05142e',
 '49/two-way/guide/dg0/ad-full/bo0/pa0': '7502bccbc275cef53f4b6ff619edafe2200e116fc97b21eea7b4b111196436c2',
 '49/two-way/guide/dg1/ad-full/bo0/pa0': 'c377150df3bce80ed667e78741123ff5b33ddfdb662c06ea7e57399a3640d42a',
 '49/two-way/latent/dg0/ad-full/bo0/pa0': 'cd0c5d06bb683a0b09b93a2ca9b01a0f8af60729e6b8b6b99f9c8234f5039493',
 '49/two-way/latent/dg1/ad-full/bo0/pa0': '4a5a84b8c29b5db9cde14c9be418bfba8130c5de49bae682183737c92c0a913a',
 '49/two-way/mixed/dg0/ad-full/bo0/pa0': '795437e51b0fe46c7e9d9473028ebcb9f47c4ef4e8c5035697f4f6b22453139c',
 '49/two-way/mixed/dg1/ad-full/bo0/pa0': 'd3374a47470ec590831d2562bb735906c81e97bf229d0b3b21180a2d33d9b7bb',
 '49/two-way20-28/frame/dg0/ad-cone/bo0/pa0': 'fef405fdde7c905bd76b79aa38f7924184eeb7d4bbb6574552e61899ed8cf398',
 '49/two-way20-28/frame/dg0/ad-cone/bo0/pa1': '9b821597834897600c98ab4a5a70459ac3e16f40e7a795cdc9891c736421076d',
 '49/two-way20-28/frame/dg0/ad-cone/bo1/pa0': '756bbb730f4c930f51182b1593706e164844822ee70147d74d3879b05d89a69c',
 '49/two-way20-28/frame/dg0/ad-cone/bo1/pa1': '1bea6b9444b6eb2acf7ece41d4b3c28ea5710533476fa3d56d0532fdb79aaa2d',
 '49/two-way20-28/frame/dg0/ad-full/bo0/pa0': 'eb2199ed369c6af3857db46cbab870b450db82000c7411669dd0c09af4da99b4',
 '49/two-way20-28/frame/dg0/ad-full/bo0/pa1': '238b39a78aaaa130be0a7ba4ef8d1e64d26bb170ac0aa4f8d65e3ad6b7be0f47',
 '49/two-way20-28/frame/dg0/ad-full/bo1/pa0': 'f0f4d18d5b3c78d1e36ae3764afb89c22643216b31f2818fc30f7c584a08b725',
 '49/two-way20-28/frame/dg0/ad-full/bo1/pa1': '39a38adbfb9f8d5ac55bfb330404ad75f651a67db127e570956771c5dead5938',
 '49/two-way20-28/frame/dg1/ad-cone/bo0/pa0': '5857cfde4dea801f7280c05ca4965eb2d69def5311d5c90e1e42a7813edeeea5',
 '49/two-way20-28/frame/dg1/ad-cone/bo0/pa1': '8f35f1f6e374be15c2f7fa6b87faa6fda7603ea25e921022034092e08c89e09d',
 '49/two-way20-28/frame/dg1/ad-cone/bo1/pa0': 'e1bd751481e258d9210f164c15a25baca41fd5fc31921d369d1fa413e6721865',
 '49/two-way20-28/frame/dg1/ad-cone/bo1/pa1': 'd845c0a468ff0b3c559421eb1f35938f58b2fda98bb49675a7ff967eafeebb8b',
 '49/two-way20-28/frame/dg1/ad-full/bo0/pa0': '3fcad6530ed3c73ec19f21e6b7cabd6438f6c65a9fa855b2d26735f4612a0b40',
 '49/two-way20-28/frame/dg1/ad-full/bo0/pa1': '3f905df243947e7ed073bcfc775ff228662a12c5417cfa4f7918ea4af99ce33b',
 '49/two-way20-28/frame/dg1/ad-full/bo1/pa0': 'ec29ece06291036f217e3f8f6c18aa0c7de6381c1c8846678b1638bf3eca3802',
 '49/two-way20-28/frame/dg1/ad-full/bo1/pa1': '4b0c54e854e7cc35c2bfd4fd4971d0e6a7cffb69fb7842febf44bb48d0400561',
 '49/two-way20-28/guide/dg0/ad-full/bo0/pa0': '6b4f435d24893190c94563b450283d25acdc61f52725df258a4480014747eb1d',
 '49/two-way20-28/guide/dg1/ad-full/bo0/pa0': 'bd6b7d53e4c58beb695bf0b1bb174dc396daa927c5a6633107397fed54d87696',
 '49/two-way20-28/latent/dg0/ad-full/bo0/pa0': '52452a1c6de02df3faf248156515fcefdcf1c21fd9eac23731674e30a7aac0a4',
 '49/two-way20-28/latent/dg1/ad-full/bo0/pa0': '25ae116d1500f95e896ce82e44146bdd8d1e53d6b65a26f049e0d1123e580b5c',
 '49/two-way20-28/mixed/dg0/ad-full/bo0/pa0': '91231a220d406295480c3d154bddc579b1d1314ac335e96f2899a3383f96c11f',
 '49/two-way20-28/mixed/dg1/ad-full/bo0/pa0': '75c4f0becb168d41ca53d6dd11c1d8a43d4379ab4d5d3d543b5252072e2e4765',
 '97/two-way/frame/dg0/ad-cone/bo0/pa0': '87a17a3f3172e9eee08ad561d86772e0d45f7c1b23dbc88e9d39ba492a92346d',
 '97/two-way/frame/dg0/ad-cone/bo0/pa1': '1777da7138cde2352d7b467b1f7a0726fcc58ac2401d2c7dc3faa2e8a270f4b6',
 '97/two-way/frame/dg0/ad-cone/bo1/pa0': '9945443f66cc5a2a62d71928c103ade495803298968684ac7599f35c24d9d25f',
 '97/two-way/frame/dg0/ad-cone/bo1/pa1': '193e9001da87310f0ce2ad00e262f141eb54b8366af3ae61df2daaf48ec9d1b1',
 '97/two-way/frame/dg0/ad-full/bo0/pa0': 'a228581d176343248ff942955cca7f5c4b4b3338b73a0a47cecc8c1ebc3cb3e2',
 '97/two-way/frame/dg0/ad-full/bo0/pa1': '6847b022bcd7d44585dca4eb3f3bb755741673c3b01914a83efa6c39fad5656b',
 '97/two-way/frame/dg0/ad-full/bo1/pa0': '460aaf418fc1e5464303286b67d04b1cc428d4ab7eb307e684054caf8f17e4a8',
 '97/two-way/frame/dg0/ad-full/bo1/pa1': '9ed641b7873e1b96c2384ea0f2a9a3d2a257c9196ec245c6d6303554ae337646',
 '97/two-way/frame/dg1/ad-cone/bo0/pa0': '3f99eefe4db63117ab7bdc8806ca1f449086c530357fade9e088de68881a3dc7',
 '97/two-way/frame/dg1/ad-cone/bo0/pa1': 'd6140c1b630ac6825208eb8bf8fcceddf3a9d43dcbfdd490cf238541feef9bcf',
 '97/two-way/frame/dg1/ad-cone/bo1/pa0': 'a5d854017d1beb4e353f29822fe7ae832d80d16cd21d8ac2905fdc5fa9632515',
 '97/two-way/frame/dg1/ad-cone/bo1/pa1': 'f5cb28340e9b4600a6922f79b0c6d2e65cf859acc159fe43059e6b3a47a06d59',
 '97/two-way/frame/dg1/ad-full/bo0/pa0': 'b2e7ea66468446a82f5c5d2ecccc4420fd7896d66d84cd051009bea6e4b52a04',
 '97/two-way/frame/dg1/ad-full/bo0/pa1': '6afdeb41ed712ad6ee59fb2e68b6db43d93905d77555d6e76febf36bd5d76ed8',
 '97/two-way/frame/dg1/ad-full/bo1/pa0': 'ce069a25d0d50d2af8adb67b16fb0a2024fbfdae1e54e09585742249e8d26e77',
 '97/two-way/frame/dg1/ad-full/bo1/pa1': 'a91049ff1409f56aa9ea1aa033565cfb411af78aff272f0aec50c91b2d37f82f',
 '97/two-way/guide/dg0/ad-full/bo0/pa0': '00567bb5a2d8a4acc8397489b6b9f81e02c9c979c19010535ca49f883ab47c9b',
 '97/two-way/guide/dg1/ad-full/bo0/pa0': '4941027ae43b72d9ea2fde20756fbedf47cb6d82dd8b7d486f744b5e508f3204',
 '97/two-way/latent/dg0/ad-full/bo0/pa0': 'fe66af8ee1c0878db53eb7ef4f077bbd2db8ae2e0fff9fd950dcd1a18f43fbb3',
 '97/two-way/latent/dg1/ad-full/bo0/pa0': '9f349db2388ccee3a6cb99b5e8502c0fb8cfadb97b9e8e4af3f326a188e47d28',
 '97/two-way/mixed/dg0/ad-full/bo0/pa0': '7223db8a42f907b619924b16e1fbcc711b4fbc35c5a893bfac11926a5bd32f3e',
 '97/two-way/mixed/dg1/ad-full/bo0/pa0': '41c0be490ec266d87878d1b165549f5a660e449d40b6fa3f64f37da38f7f8f10',
 '97/two-way20-28/frame/dg0/ad-cone/bo0/pa0': 'b8ca87ab748c70d497679425a1854063a4b967a80d4a86ea5a9e8b8bcfdc4fce',
 '97/two-way20-28/frame/dg0/ad-cone/bo0/pa1': '2b3685d4f205f02da091c03391f54d5a31a00d71709ef689b2828e036a64ff71',
 '97/two-way20-28/frame/dg0/ad-cone/bo1/pa0': '55ef1d5b56028bcf4d7dfeaaa368b410257e2d93007da28620c677de7b51cedf',
 '97/two-way20-28/frame/dg0/ad-cone/bo1/pa1': 'de2ccee56b1f5e30bdab7daf9c94fa323572687e94fbbd84a43f431acd468324',
 '97/two-way20-28/frame/dg0/ad-full/bo0/pa0': '86f50af437b154399fc674ea2972ba4aed99ebd2ac03b7ad4a3fc63ded39d398',
 '97/two-way20-28/frame/dg0/ad-full/bo0/pa1': '2ce8c6a5c8b96b8939fad58da46d021c591a4d8131f77eae67eb5fb9180a24dd',
 '97/two-way20-28/frame/dg0/ad-full/bo1/pa0': '24a9756302a2026e863f4af3a24a37f58a1752b33b6e5c10ffd975e049470271',
 '97/two-way20-28/frame/dg0/ad-full/bo1/pa1': '0adf9d5e6078d399bb0493d21dbe90a02de10638c3871be9a105c700117df96e',
 '97/two-way20-28/frame/dg1/ad-cone/bo0/pa0': '446aa56eab050faa20d71c23eb55cab35a51e1ea142dab8551254d7a7cd5bfd6',
 '97/two-way20-28/frame/dg1/ad-cone/bo0/pa1': 'aa911183870d579aa0c062276e6fb480347400a460d9783c947d06b2bbea215a',
 '97/two-way20-28/frame/dg1/ad-cone/bo1/pa0': '9d9213410c6468ebbe692b61565d3f650508c76d6486dd292e0fe69df45a8f17',
 '97/two-way20-28/frame/dg1/ad-cone/bo1/pa1': '5f5f8f7da5beeab7a119d67878e845972da58e509b695452447937d2c8bf265d',
 '97/two-way20-28/frame/dg1/ad-full/bo0/pa0': '220465c3ab354d76ed3267ef6acb589753d7528e8144313c79262ca20cbe0e64',
 '97/two-way20-28/frame/dg1/ad-full/bo0/pa1': 'ea8c2532adc17e30421fe72a62e27fd4ec9f58b2576cf79e420784e9dab871a5',
 '97/two-way20-28/frame/dg1/ad-full/bo1/pa0': '3d54c9ff88cc69aba2b900d28c57c18e96f957a2bc888ac14c90fc47c63f9851',
 '97/two-way20-28/frame/dg1/ad-full/bo1/pa1': '2de25c5fcda67b9208b1a759e7f397265ca78310856ad5bef6d2ae44b18e6c50',
 '97/two-way20-28/guide/dg0/ad-full/bo0/pa0': '0bc0a8bf0812f368aa9923c7432e8a66b19b861dc583a98bd0d1fcc67332bff8',
 '97/two-way20-28/guide/dg1/ad-full/bo0/pa0': '1d6695b6f6c37b3b7663e20f90abc755c27a948d5e0d07922b539b5cad0fba9d',
 '97/two-way20-28/latent/dg0/ad-full/bo0/pa0': '4b964aaa2ec8ad0c004000f1c80686d21cc4f750a558558f3cddf6c1be7cdb11',
 '97/two-way20-28/latent/dg1/ad-full/bo0/pa0': '5f88c2c523ea88ad039b537968f71467a23f7d085f9f6cd5151c20a977272cec',
 '97/two-way20-28/mixed/dg0/ad-full/bo0/pa0': '3bdcc8031039f70307485280e23d2bd4da0caa685f12fbc2dd30c3b46dad07fb',
 '97/two-way20-28/mixed/dg1/ad-full/bo0/pa0': '1f9331cd919a3762c9ce77c7312b9ec845d07da5fedae5ccae7967b32f477c93'}

COMMON, LAUNCHER = 'launch/encoder_runtime_common.py', 'launch/serve-encoder.py'
STATUS = (b'Packet118b = packet117 (frame anchor, the gated decoder graph, the cone anchor decode, the stage-A/B '
          b'encodes on the decode thread, 121-frame chunks) plus three launch-selectable server-side levers, each exact '
          b'by construction: the timing split of submit -> sampler A and of the receipt turnaround (measurement only), '
          b'the four-card safety snapshot from residence fingerprints bound to the admitted ones (LTX_SNAPSHOT_MODE, '
          b'dual-checked against the walk in qualification and on every 20th or near-floor stream chunk), and the '
          b'decoder-graph pool cap (LTX_DECODER_GRAPH_POOL_CAP_GB); stream118b- names; nine-capture exact qualification '
          b'gates streaming; not GPU-qualified.\n')
COMPONENTS = ('session.py', 'integration.py', 'stream_contract.py', 'stream_receipts.py', 'stream_preview.py',
              'stream_decode.py', 'latent_anchor.py',
              'qualification_gate.py', 'candidate_safety.py', 'conditioning_guard.py',
              'native_bindings.py', 'continuation_anchor.py', 'stream_decoder_graph.py',
              'stream_anchor_decode.py', 'precompute_guard.py', 'snapshot_fingerprint.py',
              'qualify_client.py', 'plan.py', 'derive_from_111.py', 'runtime_packet.py')
MODULES = {n: ('ltx_resolution_session.py' if n == 'session.py' else n) for n in COMPONENTS
           if n not in ('qualify_client.py', 'plan.py', 'derive_from_111.py', 'runtime_packet.py')}
NAME_DIRECTORIES = ('output', 'output/validation', 'requests')
GIB, MIB = 2 ** 30, 2 ** 20
RESERVE = 50 * GIB
BUILD_ALLOWANCE = 160 * MIB
RUN_ALLOWANCE = 3 * GIB
CONTROL_ENVIRONMENT = {
    'LTX_OUTPUT_SIZE': '256x256', 'LTX_BUSY_WINDOWS': '0',
    'LTX_SAMPLER_WORKERS': '1', 'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
    'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
    'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_parent_raw = (PARENT / 'manifest.json').read_bytes()
require(digest(_parent_raw) == PARENT_SHA, 'Sealed117 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
require(digest((PARENT / COMMON).read_bytes()) == _parent_manifest['files'][COMMON], 'Sealed117 checker changed')
BASE = load(PARENT / COMMON, 'stream118b_parent117')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module
NODES = list(BASE.NODES)


def __getattr__(name):
    return getattr(BASE, name)


def replace(raw, old, new, count=1):
    text = raw.decode() if isinstance(raw, bytes) else raw
    require(text.count(old) == count, 'Source anchor count differs: ' + repr(old[:90]))
    return text.replace(old, new)


# -- launch-time overrides (used by the sealed launcher through this module) ------
def latch(name, root=ROOT):
    """A lever latch file in the results root (None when absent)."""
    path = Path(root) / name
    return str(path) if path.exists() or path.is_symlink() else None


def decoder_graph_latch(root=ROOT):
    """Packet116: the decoder-graph latch a mismatch or refused capture wrote (None when absent)."""
    return latch(DECODER_GRAPH_LATCH, root)


def check_control_environment(root=ROOT):
    require(all(os.environ.get(k) == v for k, v in CONTROL_ENVIRONMENT.items()),
            'Explicit packet118b environment differs: ' + json.dumps(CONTROL_ENVIRONMENT, sort_keys=True))
    env = os.environ.get
    require(env('LTX_DECODER_GRAPH') in DECODER_GRAPH, 'LTX_DECODER_GRAPH must be set to 0 or 1')
    require(env('LTX_ANCHOR_DECODE') in ANCHOR_DECODE, 'LTX_ANCHOR_DECODE must be set to full or cone')
    require(env('LTX_BENCODE_OVERLAP') in BENCODE_OVERLAP, 'LTX_BENCODE_OVERLAP must be set to 0 or 1')
    require(env('LTX_PREP_AHEAD') in PREP_AHEAD, 'LTX_PREP_AHEAD must be set to 0 or 1')
    require(env('LTX_SNAPSHOT_MODE') in SNAPSHOT_MODES, 'LTX_SNAPSHOT_MODE must be set to walk or fingerprint')
    cap = env('LTX_DECODER_GRAPH_POOL_CAP_GB')
    if cap is not None:
        require(re.fullmatch(r'(0|[1-9][0-9]?)(\.[0-9]{1,2})?', cap) is not None and 0.25 <= float(cap) <= 16.0,
                'LTX_DECODER_GRAPH_POOL_CAP_GB must be a decimal between 0.25 and 16 (at most two decimals), or unset')
        require(env('LTX_DECODER_GRAPH') == '1', 'LTX_DECODER_GRAPH_POOL_CAP_GB needs LTX_DECODER_GRAPH=1')
    require(env('LTX_STREAM_TEXT_REUSE') in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be set to 0 or 1')
    require(env('LTX_STREAM_FRAMES') in FRAMES, 'LTX_STREAM_FRAMES must be set to 49, 97 or 121')
    require(env('LTX_SAMPLER_PLACEMENT') in PLACEMENTS, 'LTX_SAMPLER_PLACEMENT must be set to two-way or two-way20-28')
    require(env('LTX_ANCHOR') in ANCHORS, 'LTX_ANCHOR must be set to mixed, latent, frame or guide')
    require(env('LTX_ANCHOR') == 'frame' or
            (env('LTX_ANCHOR_DECODE'), env('LTX_BENCODE_OVERLAP'), env('LTX_PREP_AHEAD')) == ('full', '0', '0'),
            'The packet117 levers need LTX_ANCHOR=frame (other anchors: LTX_ANCHOR_DECODE=full, '
            'LTX_BENCODE_OVERLAP=0, LTX_PREP_AHEAD=0)')
    found = decoder_graph_latch(root)
    require(env('LTX_DECODER_GRAPH') == '0' or found is None,
            'Decoder-graph latch present (%s): a decoder-graph mismatch or refused capture was recorded; relaunch '
            'with LTX_DECODER_GRAPH=0, or archive the latch after an owner review' % found)
    found = next((p for p in (latch(n, root) for n in ANCHOR_DECODE_LATCHES) if p is not None), None)
    require(env('LTX_ANCHOR_DECODE') == 'full' or found is None,
            'Anchor-decode latch present (%s): a cone anchor differed from its full decode or the cone failed; '
            'relaunch with LTX_ANCHOR_DECODE=full, or archive the latch after an owner review' % found)
    found = next((p for p in (latch(n, root) for n in PRECOMPUTE_LATCHES) if p is not None), None)
    require((env('LTX_BENCODE_OVERLAP'), env('LTX_PREP_AHEAD')) == ('0', '0') or found is None,
            'Precompute latch present (%s): a precomputed anchor encode failed its guard or differed from the '
            'native one; relaunch with LTX_BENCODE_OVERLAP=0 LTX_PREP_AHEAD=0, or archive the latch after an '
            'owner review' % found)
    found = latch(SNAPSHOT_LATCH, root)
    require(env('LTX_SNAPSHOT_MODE') == 'walk' or found is None,
            'Snapshot latch present (%s): a fingerprint snapshot disagreed with the walk; relaunch with '
            'LTX_SNAPSHOT_MODE=walk, or archive the latch after an owner review' % found)


def expected_run_name(environ=None):
    environ = os.environ if environ is None else environ
    return RUN_NAMES.get('%s/%s/%s/dg%s/ad-%s/bo%s/pa%s/sm-%s' % tuple(environ.get(k) for k in (
        'LTX_STREAM_FRAMES', 'LTX_SAMPLER_PLACEMENT', 'LTX_ANCHOR', 'LTX_DECODER_GRAPH', 'LTX_ANCHOR_DECODE',
        'LTX_BENCODE_OVERLAP', 'LTX_PREP_AHEAD', 'LTX_SNAPSHOT_MODE')))


def name_collisions(names, prefix, root=ROOT):
    """Entries under output/, output/validation/ and requests/ that a packet118b server would collide with."""
    found = []
    for directory in NAME_DIRECTORIES:
        path = Path(root) / directory
        if not path.exists():
            continue
        require(path.is_dir() and not path.is_symlink(), 'Name directory is not a plain directory: ' + str(path))
        for entry in sorted(os.listdir(path)):
            if entry in names or entry.startswith(prefix):
                found.append(directory + '/' + entry)
    return found


def check_name_collisions(packet, root=ROOT):
    """Launcher preflight (also in --check-only): refuse when any setup/qualification name, or any
    entry with the packet's stream prefix, already exists where the server creates names."""
    contract = module(Path(packet) / 'resolution/components/stream_contract.py', 'stream118b_names')
    names, prefix = set(contract.fixed_names()), contract.RUN_PREFIX + '-'
    require(prefix == 'stream118b-' and all(n.startswith(prefix) for n in names), 'Packet118b name prefix differs')
    found = name_collisions(names, prefix, root)
    require(not found, 'Packet118b names already exist (archive them first): ' + ', '.join(found[:12]) +
            (' and %d more' % (len(found) - 12) if len(found) > 12 else ''))
    return {'checked': list(NAME_DIRECTORIES), 'fixed_names': sorted(names), 'prefix': prefix, 'collisions': []}


def admit_storage(packet, run):
    helper = module(packet / 'launch/check-storage-headroom.py', 'stream118b_storage')
    result = helper.inspect_destination(run, RESERVE, RUN_ALLOWANCE)
    require(result['admitted'], '50GiB reserve plus 3GiB stream allowance required')
    return result


# -- source transforms (applied to the sealed 116 files) ----------------------------
def geometry_source(raw, plan_sha, qids):
    """117's ltx_output_size_98.py (frames 49|97|121, ids keyed by frames/placement/anchor/decoder graph/levers):
    the 118 plan, the 118 qualification ids, mode 118."""
    t = replace(raw, "_RESOLUTION_PLAN_SHA256 = '" + PARENT_PLAN_SHA + "'", "_RESOLUTION_PLAN_SHA256 = '" + plan_sha + "'")
    tail = ("[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way') + '/' + "
            "os.environ.get('LTX_ANCHOR', 'frame') + '/dg' + os.environ.get('LTX_DECODER_GRAPH', '1') + "
            "'/ad-' + os.environ.get('LTX_ANCHOR_DECODE', 'cone') + '/bo' + "
            "os.environ.get('LTX_BENCODE_OVERLAP', '1') + '/pa' + os.environ.get('LTX_PREP_AHEAD', '1')]")
    t = replace(t, "_RESOLUTION_QUALIFICATION_ID = " + repr(PARENT_QIDS) + tail,
                "_RESOLUTION_QUALIFICATION_ID = " + repr(qids) + tail)
    t = replace(t, "_RESOLUTION_MODE = 'stream-candidate-117-v1'", "_RESOLUTION_MODE = 'stream-candidate-118b-v1'")
    ast.parse(t)
    return t.encode()


def capture_guard_source(raw):
    """117's ltx_duration_guard.py (the 121-frame capture shapes are already there): the 118 prewrite schema."""
    t = replace(raw, "'ltx.stream117-prewrite.v1'", "'ltx.stream118b-prewrite.v1'")
    ast.parse(t)
    return t.encode()


def launcher_source(raw):
    """117's serve-encoder.py: the packet name in two literals (the 118 environment rules - the levers, the
    snapshot mode, the pool cap and their latches - live in check_control_environment, which prepare_start calls
    in launch and --check-only)."""
    t = replace(raw, "                   'Packet117 admits only the 256x256 continuation stream server')",
                "                   'Packet118b admits only the 256x256 continuation stream server')")
    t = replace(t, "    # Packet117 naming rule (the 113 naming incident): refuse before any device work, also in --check-only.\n"
                   "    # Packet117: check_control_environment also refuses each lever while its latch exists.\n",
                "    # Packet118b naming rule (the 113 naming incident): refuse before any device work, also in --check-only.\n"
                "    # Packet118b: check_control_environment also refuses each lever while its latch exists.\n")
    ast.parse(t)
    return t.encode()


# -- assembly -------------------------------------------------------------------
def check_plan(raw):
    envelope = json.loads(raw)
    require(envelope['plan_sha256'] == PLAN_SHA == digest(canonical(envelope['plan'])) and
            envelope['plan']['qualification_ids'] == QIDS, 'Reviewed118 plan changed')
    return envelope['plan']


def input_inventory():
    files = {n: sha(AUTHOR / n) for n in COMPONENTS}
    check_plan(regular(PLAN))
    files['stream-plan.json'] = sha(PLAN)
    files[REFERENCE_SOURCE] = sha(AUTHOR / REFERENCE_SOURCE)
    return files


def check_reference(raw):
    value = json.loads(raw)
    require(value.get('schema') == 'ltx.stream116.reference-frame-hashes.v1' and
            set(value.get('variants', {})) == {'49/two-way20-28/frame', '97/two-way20-28/frame'} and
            all(len(v['chunks']) == 3 and v['verdict_passed'] is True for v in value['variants'].values()),
            'Reference hash document differs')
    return raw


def successor_files(component_dir, plan_raw, reference_raw):
    check_plan(plan_raw)
    result = {'provenance/packet117-manifest.json': regular(PARENT / 'manifest.json'),
              'resolution/stream-plan.json': plan_raw, REFERENCE_PATH: check_reference(reference_raw)}
    require(digest(result['provenance/packet117-manifest.json']) == PARENT_SHA, 'Parent manifest changed')
    for name in COMPONENTS:
        raw = regular(component_dir / name)
        ast.parse(raw)
        result['resolution/components/' + name] = raw
        if name in MODULES:
            result['source/scripts/' + MODULES[name]] = raw
    result[COMMON] = regular(component_dir / 'runtime_packet.py')
    result[LAUNCHER] = launcher_source(regular(PARENT / LAUNCHER))
    result['source/scripts/ltx_output_size_98.py'] = geometry_source(
        regular(PARENT / 'source/scripts/ltx_output_size_98.py'), PLAN_SHA, QIDS)
    result['source/scripts/ltx_duration_guard.py'] = capture_guard_source(
        regular(PARENT / 'source/scripts/ltx_duration_guard.py'))
    # Components identical to the sealed 117 copies are not 'changed' (they stay inherited).
    for path in [p for p in result if p in _parent_manifest['files']]:
        if digest(result[path]) == _parent_manifest['files'][path]:
            del result[path]
    for path, raw in result.items():
        if path.endswith('.py'):
            ast.parse(raw)
    return result


def manifest_files(parent, changed):
    files = dict(parent['files'])
    for path, raw in changed.items():
        if path in parent['files']:
            files['provenance/packet117/' + path] = parent['files'][path]
        files[path] = digest(raw)
    return files


def transition(parent, changed, inventory, admission):
    return {'schema': 'ltx.stream118b.transition.v1', 'packet_revision': '118b',
            'supersedes': {'packet': 118, 'manifest_sha256': 'cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6',
                           'status': 'withdrawn-never-launched'},
            'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA,
            'plan_sha256': PLAN_SHA, 'qualification_ids': QIDS, 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)),
            'source_delta': {p: {'before_sha256': parent['files'].get(p), 'after_sha256': digest(raw)}
                             for p, raw in changed.items()},
            'control': {'size': '256x256', 'frame_count': 'LTX_STREAM_FRAMES (49, 97 or 121; first recommendation: 121 dg0)',
                        'fps': 24, 'layout': 'LTX_SAMPLER_PLACEMENT (two-way or two-way20-28; launched two-way20-28)',
                        'anchor': 'LTX_ANCHOR (frame = packet113 decoded-frame anchor at both stages; mixed, '
                                  'latent and guide kept for A/B with the levers off)',
                        'workers': 1, 'batch': 1, 'shared_pool': 1,
                        'decode_replica_env': 'xpu:2 (environment only; native VAEDecode, zero replicas)',
                        'decoder_graph_capture': 'LTX_DECODER_GRAPH (set explicitly): forward_pre_diffusion and '
                                                 'forward_diff_step graph replay on xpu:3, one shared pool, bounded '
                                                 'rope/axis-mask/noise caches; qualified by byte identity against the '
                                                 'uncached eager decode; latch file refuses graph mode after a mismatch',
                        'anchor_decode': 'LTX_ANCHOR_DECODE (full|cone, set explicitly; frame only): cone = the '
                                         'anchor from a native VAEDecode whose stage-5 step issues only the calls '
                                         'the last pixel frame depends on; the full display decode follows on the '
                                         'decode thread after the successor\'s sampler A starts and must match the '
                                         'anchor byte for byte (else latch anchor-decode-118-refused.json; the '
                                         'launcher also honours anchor-decode-117-refused.json)',
                        'bencode_overlap': 'LTX_BENCODE_OVERLAP (0|1, set explicitly; frame only): the stage-B '
                                           'anchor encode on the decode thread beside stage A between xpu:3-only '
                                           'safety snapshots; the stage-B node runs the native node with it inside '
                                           'the unchanged four-card guard (graph chain: dual-checked against the '
                                           'native encode; else latch precompute-118-refused.json; the launcher '
                                           'also honours precompute-117-refused.json)',
                        'prep_ahead': 'LTX_PREP_AHEAD (0|1, set explicitly; frame only): the stage-A anchor encode '
                                      'on the decode thread after the predecessor receipt commits, same guard',
                        'decode': 'one ordered decode thread on xpu:3, bounded FIFO, back-pressure, latch; '
                                  'frame: anchor decode -> anchor file -> hand-off -> [stage-A encode] -> [wait for '
                                  'the successor sampler A, stage-B encode] -> [display decode + byte check] -> '
                                  'audio, hashes, record, preview; sharpness profile per chunk',
                        'encoder_lock': 'prompt-thread conditioning-guard calls and the decode thread\'s encodes '
                                        'never overlap',
                        'mixed_wait': 'stage-B condition node waits (bounded 300 s) for the predecessor decode',
                        'preview': 'one bounded FIFO writer thread behind the decode thread',
                        'chain_reset': 'stream chunk reset=1 is unanchored (stream_seq 0 form)',
                        'graph_replay': 'LTXGraphCaptureGate all48 chain1', 'qualification_requests': 9,
                        'full_captures': 9, 'stream_requests': 'unbounded, serial, storage-bounded',
                        'environment': CONTROL_ENVIRONMENT, 'text_reuse_env': 'LTX_STREAM_TEXT_REUSE (set explicitly)',
                        'names': 'stream118b- prefix; launcher refuses existing names (also --check-only)',
                        'timing_split': 'always on, measurement only: receipts split submit -> sampler A '
                                        '(stream_receipts.SUBMIT_SPLIT), list the four-card snapshots with their '
                                        'durations, count the authority healthy() calls and split the predecessor '
                                        'receipt -> this submit (TURNAROUND_SPLIT)',
                        'snapshot_mode': 'LTX_SNAPSHOT_MODE (walk|fingerprint, set explicitly; run-name token '
                                         '-sm<walk|fp>-): fingerprint = residence/ownership and sampler placement from '
                                         'fact tuples bound at the placement event to the admitted fingerprints (the '
                                         'walk whenever a fact differs); setup and qualification dual-run every '
                                         'snapshot, streaming every 20th chunk and from any inclusive near-floor reading on; decode-thread P7 always dual; a '
                                         'disagreement latches snapshot-118-refused.json',
                        'decoder_graph_pool_cap': 'LTX_DECODER_GRAPH_POOL_CAP_GB (optional, dg1 only): methods are '
                                                  'captured in first-call order while the measured reserved growth of '
                                                  'the captures already made is below the cap; a capped method runs '
                                                  'eagerly with the same caches (byte-gated)',
                        'na_axis_router': 'decoder-graph and cone installers accept the pinned '
                                          'ltx_na_axis_router.AxisRouter (sha 1fe42fe9...) in its no-scope route to '
                                          'the eager na3d',
                        'reference_hashes': REFERENCE_PATH,
                        'stage_overlap_across_cards': 'not in 118'},
            'storage_admission': admission, 'qualification': False, 'model_requests': 0,
            'claims': {'quality_adopted': False, 'seam_accepted': False, 'audio_alignment_resolved': False,
                       'speed_improvement': False, 'decoder_graph_exact_on_xpu': False,
                       'cone_exact_on_xpu': False, 'precompute_exact_on_xpu': False, 'geometry_121_measured': True,
                       'snapshot_fingerprint_equivalence_on_xpu': False, 'decoder_pool_cap_fits_121_dg1': False}}


def semantic_manifest(parent, files, change):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.continuation-stream-runtime.v3', files=files,
                  preparer_sha256=files['resolution/components/runtime_packet.py'], resolution101=change)
    result['startup_tools'] = {Path(k).name: files[k] for k in (COMMON, LAUNCHER)}
    for name in list(result['extension_sha256s']):
        path = 'source/scripts/' + name
        if path in files:
            result['extension_sha256s'][name] = files[path]
    for name in MODULES.values():
        result['extension_sha256s'][name] = files['source/scripts/' + name]
    result['output_size']['module_sha256'] = files['source/scripts/ltx_output_size_98.py']
    result['output_size']['stream118b'] = {'plan_sha256': PLAN_SHA, 'size': '256x256', 'frame_count': [49, 97, 121],
                                          'anchor': list(ANCHORS), 'default_anchor': 'frame',
                                          'decoder_graph': [0, 1], 'default_decoder_graph': 1,
                                          'anchor_decode': list(ANCHOR_DECODE), 'bencode_overlap': [0, 1],
                                          'prep_ahead': [0, 1], 'default_levers': ['cone', 1, 1],
                                          'snapshot_mode': list(SNAPSHOT_MODES), 'default_snapshot_mode': 'fingerprint',
                                          'decoder_graph_pool_cap_gb': 'unset or 0.25..16',
                                          'comparison_mode': 'stream-candidate-118b-v1', 'qualified': False,
                                          'numerics_from': 'packet117 (the 118 levers change no arithmetic)'}
    return result


def assembly_bytes(parent, changed):
    original = sum((PARENT / p).stat().st_size for p in parent['files'])
    return original + sum(len(raw) for raw in changed.values()) + len(STATUS)


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or ''),
            'Unexpected118 packet or manifest identity')
    require(sha(packet / 'manifest.json') == expected_manifest_sha256, '118 manifest changed')
    manifest = json.loads(regular(packet / 'manifest.json'))
    require(regular(packet / 'STATUS.txt') == STATUS, '118 status identity changed')
    require(type(manifest.get('files')) is dict, '118 file inventory missing')
    for path, expected in manifest['files'].items():
        require(type(path) is str and type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected)
                and sha(safe_path(packet, path)) == expected, '118 file changed before component import: ' + str(path))
    require(all('resolution/components/' + n in manifest['files'] for n in COMPONENTS),
            '118 component inventory incomplete')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(packet / 'resolution/components', regular(packet / 'resolution/stream-plan.json'),
                              regular(packet / REFERENCE_PATH))
    expected_files = manifest_files(parent, changed)
    require(manifest['files'] == expected_files, '118 source closure differs')
    checker_path = 'provenance/source99/check-upstream-source-99.py'
    require(sha(PARENT / checker_path) == parent['files'][checker_path], 'Inventory checker changed')
    checker = module(PARENT / checker_path, 'stream118b_inventory')
    require(checker.inventory(packet) == set(expected_files) | {'manifest.json', 'STATUS.txt'},
            'Unbound118 packet file')
    inventory = {n: expected_files['resolution/components/' + n] for n in COMPONENTS}  # all bound
    inventory['stream-plan.json'] = expected_files['resolution/stream-plan.json']
    inventory[REFERENCE_SOURCE] = expected_files[REFERENCE_PATH]
    admission = manifest['resolution101']['storage_admission']
    require(admission['admitted'] is True, '118 build was not admitted')
    change = transition(parent, changed, inventory, admission)
    require(manifest == semantic_manifest(parent, expected_files, change), '118 semantic identity differs')
    return manifest


def write_new(path, raw, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
        os.fchmod(stream.fileno(), mode)
        stream.flush()
        os.fsync(stream.fileno())


def inspect_assembly():
    inventory = input_inventory()
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN), regular(AUTHOR / REFERENCE_SOURCE))
    require(input_inventory() == inventory, 'Authored inputs changed during assembly')
    amount = assembly_bytes(parent, changed)
    require(amount + 4 * MIB < BUILD_ALLOWANCE, 'Source assembly exceeds the build allowance')
    return {'status': 'source-assembly-checked', 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)), 'source_payload_bytes': amount,
            'build_allowance_bytes': BUILD_ALLOWANCE, 'run_allowance_bytes': RUN_ALLOWANCE,
            'changed_files': {p: digest(raw) for p, raw in changed.items()},
            'materialized': False, 'model_requests': 0}


def build(expected_inventory_sha256):
    inspected = inspect_assembly()
    require(inspected['input_inventory_sha256'] == expected_inventory_sha256, 'Reviewed118 inputs differ')
    require(not PACKET.exists() and not PACKET.is_symlink() and
            not any(p.is_symlink() for p in PACKET.parents), 'Exclusive regular packet destination required')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN), regular(AUTHOR / REFERENCE_SOURCE))
    inventory = input_inventory()
    require(inventory == inspected['input_inventory'], 'Inputs changed after review')
    helper = module(PARENT / 'launch/check-storage-headroom.py', 'stream118b_build_storage')
    admission = helper.inspect_destination(PACKET, RESERVE + RUN_ALLOWANCE, BUILD_ALLOWANCE)
    require(admission['admitted'], '50GiB reserve plus 3GiB run plus 160MiB build allowance required')
    PACKET.mkdir(mode=0o700)
    write_new(PACKET / 'STATUS.txt', STATUS)
    for path, expected in parent['files'].items():
        raw = regular(PARENT / path)
        require(digest(raw) == expected, 'Parent file changed while copying: ' + path)
        mode = stat.S_IMODE((PARENT / path).stat().st_mode)
        if path in changed:
            write_new(PACKET / 'provenance/packet117' / path, raw, mode)
            raw = changed[path]
        write_new(PACKET / path, raw, mode)
    for path, raw in changed.items():
        if path not in parent['files']:
            write_new(PACKET / path, raw)
    files = manifest_files(parent, changed)
    change = transition(parent, changed, inventory, admission)
    manifest = semantic_manifest(parent, files, change)
    write_new(PACKET / 'manifest.json', json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode() + b'\n')
    for directory in [p for p in PACKET.rglob('*') if p.is_dir()] + [PACKET, PACKET.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    manifest_sha = sha(PACKET / 'manifest.json')
    verify_packet(PACKET, manifest_sha)
    return {'status': 'prepared-not-GPU-qualified', 'packet': str(PACKET), 'manifest_sha256': manifest_sha,
            'input_inventory_sha256': expected_inventory_sha256, 'storage_admission': admission,
            'model_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--input-inventory-sha256')
    parser.add_argument('--inspect-assembly', action='store_true')
    parser.add_argument('--verify-manifest-sha256')
    args = parser.parse_args()
    require(sum((args.build, args.inspect_assembly, bool(args.verify_manifest_sha256))) <= 1, 'Select one operation')
    if args.build:
        result = build(args.input_inventory_sha256)
    elif args.inspect_assembly:
        result = inspect_assembly()
    elif args.verify_manifest_sha256:
        verify_packet(PACKET, args.verify_manifest_sha256)
        result = {'status': 'source-closure-verified', 'model_requests': 0}
    else:
        inventory = input_inventory()
        result = {'status': 'plan-only', 'packet': str(PACKET), 'input_inventory': inventory,
                  'input_inventory_sha256': digest(canonical(inventory)), 'materialized': False,
                  'model_requests': 0}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
