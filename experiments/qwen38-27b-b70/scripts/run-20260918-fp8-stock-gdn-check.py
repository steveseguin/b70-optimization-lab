#!/usr/bin/env python3
"""Stock-vs-lab GDN rounding check (2026-09-18): does the pristine vllm/vllm-openai-xpu image produce the same no-MTP
output as the lab's r312d-c image, prompt for prompt?

Why this exists
---------------
Every lab image since r309 rebuilt `_xpu_C` -- which contains the *stock* gated-delta-net (GDN) kernel, not just our
own -- against sycl-tla `cd76379`, whichever revision the build tree happened to have checked out. The attention
library moved at the ULP level when its CUTLASS pin moved (see notes/2026-09-16-fp8-review-findings.md, "the 7.6e-6
gap was the sycl-tla revision"), so the same may be true of the GDN kernel. Nothing shipped is invalidated by that --
every gate in the one-card package is same-image, candidate against reference on the same binary -- but the question
"are the one-card package's no-MTP outputs the same tokens the pristine upstream image would have produced?" has never
been measured. This runner measures it.

  If the two agree 12/12: the `_xpu_C` rebuild is output-neutral and nothing follows.
  If they differ: the candidate fix is an r313 rebuild of `_xpu_C` against the pinned revision
  (`87f6850` for vllm-xpu-kernels 0.1.14.1, read from the kernel's own CMakeLists CUTLASS_REVISION,
  variant-c toolchain), followed by the full acceptance again.

Shape of the run (modelled on run-20260918-fp8-lc3-campaign.py)
--------------------------------------------------------------
Two research servers, one after the other, never together, on ONE card (`--gpu 0`), both in the same configuration:

  no MTP, 32,768 context at 0.983, batched 2048, host embedding (`--cpu-embed`), and NO lab overlays that need
  lab-built kernels -- no `b70-gdn-checkpoint`, no `b70-fa-multiq`, no `--fa-verify-rows`, no INT4 draft/shortlist.

  arm `stock`    the pristine base image sha256:96db42e2...  (vllm/vllm-openai-xpu)
  arm `r312dc`   the lab image         sha256:ea61e698...    (the shipped one-card package's image)

`--cpu-embed` stays ON for both. It is the only overlay here and it is pure Python (a read-only bind mount at
/overlay plus PYTHONPATH and B70_CPU_EMBED=1); it needs no lab-built kernel. It is kept because it is what the shipped
one-card package runs, so agreeing with the stock image *with* it is the statement we actually want. If the stock
image's vLLM lays its modules out differently, the overlay will fail to patch and the arm will not come ready -- which
this runner records as "stock image lacks the overlay's prerequisites", NOT as a rounding verdict. See `audit_images`.

Then: the strict suite on each arm, each compared (a) against the other, prompt by prompt, which is the verdict, and
(b) against the R311b 896-block no-MTP reference, which is the same reference every shipped 32K gate used, for
context. Finally the two-card FP8 service goes back on 18124 exactly as the lc-3/lc-4 runners restore it.

  verdict.json   {'verdict': 'identical' | 'DIFFERS' | 'not measured', ...}

Running it
----------
This is a GPU campaign. It is queued by the USER, after the fault halt is lifted, never started from an interactive
harness (the harness kills long jobs):

    systemd-run --user --unit fp8-stock-gdn-20260918 --working-directory /home/steve/b70-optimization-lab --collect \
        --setenv=SERVICE_STATE=<the state dir of whatever service is up right now> \
        --setenv=CAMPAIGN_OUT=/mnt/fast-ai/bench-results/fp8-stock-gdn-20260918 \
        python3 experiments/qwen38-27b-b70/scripts/run-20260918-fp8-stock-gdn-check.py

It stops the running two-card service first (through the same serve.py that started it, after waiting for `ready`),
runs a health probe, and refuses to go on if that probe fails. Any GPU fault line in the journal halts it with rc 3
and NO service restore -- deliberately, so the evidence is untouched for the user.

Preconditions, all checked before a container starts:
  * no card holds an uncleared device coredump (the 2026-09-18 fault halt);
  * both images exist locally (`docker image inspect`);
  * the two images' baked env/cmd/labels are recorded and diffed, so a version skew between them is visible in the
    receipts rather than silently spoiling the comparison.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/home/steve/b70-optimization-lab')
OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-stock-gdn-20260918'))
os.environ['CAMPAIGN_OUT'] = str(OUT)

spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])

# The pristine upstream image, as pinned in the findings note. Local tag on this host: vllm/vllm-openai-xpu:latest.
STOCK = 'sha256:96db42e248d48760a4937eb3d04c4878b39d13a9814efea95d510393e097a901'
# The shipped one-card package's image (r312d-c). Local tag: neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r312d-c-multiq.
R312DC = os.environ.get('R312DC_IMAGE', 'sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a')

PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
# The R311b 896-block no-MTP reference: the same one every shipped 32K gate was measured against.
CKPT2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-ckpt2-20260917/tp1-mtp0-b896-strict')
# The two-card service's own reference (comm-2, no MTP), used for the restore check at the end.
COMM2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict')

# One card, no MTP, 32,768 at 0.983, host embedding. NO overlay that needs a lab-built kernel.
# (--cpu-embed is pure Python; --mtp defaults to 0, so no --speculative-config is passed at all.)
def arm_args(image):
    return ['--tp', '1', '--gpu', '0', '--batched', '2048', '--cpu-embed',
            '--mem', '0.983', '--max-model-len', '32768', '--image', image]


ARMS = [('stock', 18220, STOCK), ('r312dc', 18221, R312DC)]


def inspect(image):
    result = R.helper.run(['docker', 'image', 'inspect', image], check=False)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)[0]


def audit_images():
    """Read-only prerequisite audit. Records both images' identity and diffs what the launcher will inherit.

    The launcher (`run-fp8-tp1-server.py`) builds its container env by SUBTRACTING the candidate image's own baked env
    from the qualified reference record's env, so a difference in baked env between the two images changes which
    variables are passed explicitly. That is correct behaviour, but it has to be visible: if the two images carry
    different vLLM versions this is not a GDN-rounding measurement at all, it is a version comparison, and the verdict
    has to say so.
    """
    audit = {'images': {}, 'warnings': []}
    for name, image in (('stock', STOCK), ('r312dc', R312DC)):
        info = inspect(image)
        if info is None:
            audit['warnings'].append(f'{name}: image {image} is NOT present locally (docker image inspect failed)')
            audit['images'][name] = None
            continue
        config = info.get('Config', {})
        audit['images'][name] = {
            'id': info.get('Id'), 'repo_tags': info.get('RepoTags'), 'created': info.get('Created'),
            'labels': config.get('Labels') or {}, 'entrypoint': config.get('Entrypoint'),
            'cmd': config.get('Cmd'), 'workdir': config.get('WorkingDir'),
            'env': sorted(config.get('Env') or []),
        }
    stock, lab = audit['images'].get('stock'), audit['images'].get('r312dc')
    if stock and lab:
        s, l = set(stock['env']), set(lab['env'])
        audit['env_only_in_stock'] = sorted(s - l)
        audit['env_only_in_r312dc'] = sorted(l - s)
        if stock['entrypoint'] != lab['entrypoint']:
            audit['warnings'].append(f"entrypoints differ: stock {stock['entrypoint']} vs r312dc {lab['entrypoint']}")
        # A vLLM version skew makes the whole comparison mean something else.
        def version_label(img):
            for key in ('org.opencontainers.image.version', 'vllm.version', 'version'):
                if key in (img['labels'] or {}):
                    return img['labels'][key]
            return None
        if version_label(stock) != version_label(lab):
            audit['warnings'].append(
                f'image version labels differ (stock {version_label(stock)!r} vs r312dc {version_label(lab)!r}); '
                'a vLLM version skew means this measures more than the _xpu_C rebuild')
    # The vLLM version each image actually imports. CPU-only probe: no --device, no model, no GPU touched.
    for name, image in (('stock', STOCK), ('r312dc', R312DC)):
        if not audit['images'].get(name):
            continue
        probe = R.helper.run(
            ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', image, '-c',
             'import vllm, sys, json; print(json.dumps({"vllm": vllm.__version__, "file": vllm.__file__, '
             '"python": sys.version.split()[0]}))'],
            check=False, timeout=180)
        try:
            audit['images'][name]['vllm'] = json.loads(probe.stdout.strip().splitlines()[-1])
        except Exception:
            audit['images'][name]['vllm'] = {'error': (probe.stdout + probe.stderr).strip()[-400:]}
    sv = (audit['images'].get('stock') or {}).get('vllm', {})
    lv = (audit['images'].get('r312dc') or {}).get('vllm', {})
    if sv.get('vllm') and lv.get('vllm') and sv['vllm'] != lv['vllm']:
        audit['warnings'].append(f"vLLM versions differ: stock {sv['vllm']} vs r312dc {lv['vllm']}")
    if sv.get('file') and lv.get('file') and sv['file'] != lv['file']:
        audit['warnings'].append(
            f"vllm import path differs: stock {sv['file']} vs r312dc {lv['file']}; the b70_cpu_embed overlay "
            'patches by module name, but a second vllm copy in the image can shadow it (see the R276 precedent)')
    (OUT / 'image-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    for line in audit['warnings']:
        R.log(f'IMAGE AUDIT WARNING: {line}')
    return audit


def coredump_cards():
    return [str(p) for p in sorted(Path('/sys/class/drm').glob('card*/device/devcoredump/data'))]


def compare_arms(results):
    """Prompt-by-prompt comparison of the two arms' strict outputs. This is the verdict."""
    a, b = OUT / 'stock-strict', OUT / 'r312dc-strict'
    if not (a.exists() and b.exists()):
        return {'verdict': 'not measured', 'reason': 'one or both arms produced no strict output'}
    out = OUT / 'stock-vs-r312dc.json'
    R.sh([sys.executable, R.COMPARE_STRICT, a, b, '--output', out], 'stock-vs-r312dc', 300)
    if not out.exists():
        return {'verdict': 'not measured', 'reason': 'compare-strict-attempt-outputs.py produced no output'}
    c = json.loads(out.read_text())['comparison']
    exact, total = c['exact_prompts'], c['total_prompts']
    return {
        'verdict': 'identical' if exact == total else 'DIFFERS',
        'exact': f'{exact}/{total}',
        'complete_token_arrays_exact': c.get('complete_token_arrays_exact'),
        'divergent_prompts': c.get('divergent_prompts', [])[:12],
        'stock_tok_s': results['stock'].get('strict', {}).get('tok_s_1_100'),
        'r312dc_tok_s': results['r312dc'].get('strict', {}).get('tok_s_1_100'),
        'comparison_file': str(out),
    }


def restore_service(results, since):
    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        R.log('service health probe failed; NOT starting the service')
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = os.environ.get('CAMPAIGN_UNIT', 'fp8-service-20260918-stock-gdn')
    argv = ['systemd-run', '--user', '--unit', unit, '--working-directory', str(ROOT), '--collect',
            sys.executable, str(PKG_TP2), 'start', '--model-dir', str(R.MODEL),
            '--state-dir', str(state_dir), '--port', '18124']
    R.wait_port_free(18124)
    (OUT / 'service.command.json').write_text(json.dumps({'argv': argv, 'started': R.now()}) + '\n')
    subprocess.run(argv, check=True)
    deadline = time.monotonic() + 2400
    state = {}
    while time.monotonic() < deadline:
        if (state_dir / 'state.json').exists():
            state = json.loads((state_dir / 'state.json').read_text())
            if state.get('status') in ('ready', 'failed', 'stopped'):
                break
        time.sleep(10)
    results['service'] = {'status': state.get('status'), 'error': state.get('error'),
                          'unit': unit, 'state_dir': str(state_dir)}
    R.log(f'service: {state.get("status")} {state.get("error") or ""}')
    if state.get('status') == 'ready':
        results['service']['strict'] = R.strict('http://127.0.0.1:18124', 'service', COMM2_STRICT)
    R.save_results()
    R.fault_check(since)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    R.log(f'stock-vs-lab GDN check start; git {head}; stock {STOCK[:19]} lab {R312DC[:19]}')
    results = R.RESULTS
    results['started'] = since
    results['images'] = {'stock': STOCK, 'r312dc': R312DC}

    dumps = coredump_cards()
    if dumps:
        R.log(f'REFUSING: uncleared device coredump: {dumps}')
        results['refused'] = {'reason': 'uncleared device coredump', 'paths': dumps}
        R.save_results()
        raise SystemExit(4)

    for path in (R.LAUNCHER, PKG_TP2, R.STRICT, R.COMPARE_STRICT, R.HEALTH, R.XPU_PYTHON, R.MODEL, CKPT2_STRICT, COMM2_STRICT):
        if not Path(path).exists():
            raise SystemExit(f'missing prerequisite: {path}')

    results['image_audit'] = audit_images()
    if any(v is None for v in results['image_audit']['images'].values()):
        R.log('REFUSING: an image named above is not present locally; pull it first')
        R.save_results()
        raise SystemExit(4)
    R.save_results()

    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    for name, port, image in ARMS:
        srv = R.Research(name, port, arm_args(image))
        r = results[name] = {'image': image,
                             'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if srv.ready:
            r['strict'] = R.strict(srv.base, name, CKPT2_STRICT)
            R.log(f"{name}: strict vs R311b-896-no-MTP {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
        else:
            R.log(f'{name}: NOT ready ({srv.state.get("error")}); no strict suite on this arm')
            if name == 'stock':
                r['note'] = ('the pristine image did not come ready in this configuration -- read '
                             f'{OUT / (name + "-owner.log")} before reading anything into the verdict; a failure to '
                             'patch b70_cpu_embed, or a serve flag the stock build does not accept, is a '
                             'prerequisite result, not a rounding result')
        R.save_results()
        r['stop'] = srv.stop()
        R.save_results()
        R.fault_check(since)
        R.wait_gpus_free()

    results['verdict'] = compare_arms(results)
    (OUT / 'verdict.json').write_text(json.dumps(results['verdict'], indent=2) + '\n')
    R.log(f"VERDICT: {results['verdict']['verdict']} ({results['verdict'].get('exact')})")
    if results['verdict']['verdict'] == 'DIFFERS':
        R.log('the _xpu_C rebuild moved the no-MTP outputs; candidate fix is an r313 rebuild against the pinned '
              'CUTLASS revision 87f6850 (variant-c toolchain), then the full acceptance again')
    R.save_results()

    restore_service(results, since)
    results['finished'] = R.now()
    R.save_results()
    R.log('=== stock-vs-lab GDN check complete ===')


if __name__ == '__main__':
    main()
