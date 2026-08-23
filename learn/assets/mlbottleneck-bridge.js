/* neural.download ↔ ML Bottleneck bridge.
 *
 * Loads the ML Bottleneck physics engine (the SDK published from
 * mlbottleneck.com, same author) and renders PROJECTIONS next to the lab's
 * measurements. Nothing here is a lab measurement: every number the bridge
 * draws is labeled as a model projection, and the page degrades to its
 * static content if the SDK cannot be loaded.
 *
 * Used by index.html (headroom grades + Intel mini-planner) and
 * learn/hardware.html (projected cross-hardware comparison).
 */
(function () {
  'use strict';

  const SDK_URL = 'https://mlbottleneck.com/dist/mlbottleneck-engine.umd.js';
  const EVIDENCE_URL = 'https://mlbottleneck.com/dist/localmaxxing-snapshot.json';
  const PLANNER_URL = 'https://mlbottleneck.com/';

  let enginePromise = null;

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      if (window.MLBottleneck) { resolve(); return; }
      const script = document.createElement('script');
      script.src = url;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('SDK failed to load'));
      document.head.appendChild(script);
    });
  }

  async function loadEngine() {
    if (enginePromise) return enginePromise;
    enginePromise = (async () => {
      await loadScript(SDK_URL);
      if (!window.MLBottleneck || typeof window.MLBottleneck.createEngine !== 'function') throw new Error('SDK missing');
      let snapshot = null;
      try {
        const response = await fetch(EVIDENCE_URL, { mode: 'cors' });
        if (response.ok) snapshot = await response.json();
      } catch (error) {
        snapshot = null; // uncalibrated predictions still work
      }
      const engine = window.MLBottleneck.createEngine(snapshot ? { snapshot } : {});
      engine.__hasEvidence = Boolean(snapshot);
      return engine;
    })();
    return enginePromise;
  }

  function fmt(value, digits) {
    if (!Number.isFinite(value)) return '—';
    if (value >= 1000) return Math.round(value).toLocaleString();
    return value.toFixed(digits === undefined ? (value >= 100 ? 0 : 1) : digits);
  }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function parseSpec(value) {
    if (!value || value === 'none') return null;
    const [method, tokens] = String(value).split(':');
    const spec = { method };
    if (parseInt(tokens, 10) > 0) spec.tokens = parseInt(tokens, 10);
    return spec;
  }

  function plannerLink(request) {
    const params = new URLSearchParams();
    params.set('model', request.model);
    const hardware = Array.isArray(request.hardware) ? request.hardware[0] : request.hardware;
    params.set('hardware', typeof hardware === 'string' ? hardware : hardware.template);
    params.set('count', String((typeof hardware === 'object' && hardware.count) || 1));
    if (request.quantFamily) params.set('quant', request.quantFamily);
    if (request.quantization) params.set('format', request.quantization);
    if (request.runtime) params.set('runtime', request.runtime);
    if (request.promptTokens) params.set('prompt', String(request.promptTokens));
    if (request.outputTokens) params.set('output', String(request.outputTokens));
    if (request.speculation) params.set('spec', request.speculation.method + (request.speculation.tokens ? ':' + request.speculation.tokens : ''));
    return PLANNER_URL + '?' + params.toString() + '#plan';
  }

  // Measured rate versus the model's "tuned-run target" (what strong runs of
  // this stack reach) — the grade is about optimization headroom, not quality.
  function grade(ratio) {
    if (!Number.isFinite(ratio)) return { letter: '—', note: 'not modeled' };
    if (ratio >= 0.9) return { letter: 'A+', note: 'at or beyond the tuned-run target' };
    if (ratio >= 0.7) return { letter: 'A', note: 'near the tuned-run target' };
    if (ratio >= 0.5) return { letter: 'B', note: 'solid; some headroom' };
    if (ratio >= 0.3) return { letter: 'C', note: 'meaningful headroom' };
    return { letter: 'D', note: 'large headroom' };
  }

  function limiterText(result) {
    const device = result.devices && result.devices[0];
    const binding = device && device.coreBinding;
    const dominant = result.bottleneck;
    if (dominant === 'memory') return 'memory bandwidth (weight reads)';
    if (dominant === 'compute') return binding === 'attention' ? 'attention over the context window' : 'compute';
    if (dominant === 'runtime') return 'runtime / kernel overhead';
    if (dominant === 'coordination') return 'cross-card coordination';
    if (dominant === 'draft') return 'draft passes';
    return dominant || 'memory bandwidth';
  }

  function barRow(label, value, max, cls, extra) {
    const width = Number.isFinite(value) && max > 0 ? Math.max(2, Math.min(100, (value / max) * 100)) : 0;
    return '<div class="hr-bar-row">'
      + '<span class="hr-bar-label">' + esc(label) + '</span>'
      + '<span class="hr-bar-track"><span class="hr-bar ' + cls + '" style="width:' + width.toFixed(1) + '%"></span></span>'
      + '<span class="hr-bar-value">' + esc(fmt(value)) + (extra ? ' <small>' + esc(extra) + '</small>' : '') + '</span>'
      + '</div>';
  }

  function requestFromDataset(data) {
    const promptTokens = Number(data.mlPrompt);
    const outputTokens = Number(data.mlOutput);
    if (!Number.isInteger(promptTokens) || promptTokens <= 0
        || !Number.isInteger(outputTokens) || outputTokens <= 0) return null;
    const request = {
      model: data.mlModel,
      hardware: { template: data.mlHardware || 'Intel Arc Pro B70', count: parseInt(data.mlCards, 10) || 1 },
      quantization: data.mlQuant || 'q4',
      runtime: data.mlRuntime || 'auto',
      promptTokens,
      outputTokens,
      speculation: parseSpec(data.mlSpec)
    };
    if (data.mlStrategy) request.strategy = data.mlStrategy;
    if (data.mlCpuMoe) request.cpuMoeLayers = parseInt(data.mlCpuMoe, 10);
    return request;
  }

  function deploymentLabel(data) {
    return [data.mlCards + '× ' + (data.mlHardwareLabel || 'B70'), data.mlQuantLabel || data.mlQuant, data.mlRuntimeLabel || data.mlRuntime].filter(Boolean).join(' · ');
  }

  // Measured vs stock projection vs tuned target vs physical ceiling, plus the grade.
  function buildHeadroomCard(engine, request, measured, title, deployment) {
    let result;
    try {
      result = engine.predict(request);
    } catch (error) {
      return null;
    }
    const target = result.ceiling ? result.ceiling.optimizedTokensPerSecond : null;
    const physical = result.ceiling ? result.ceiling.physicalTokensPerSecond : null;
    const stock = result.ceiling ? result.ceiling.expectedTokensPerSecond : result.decode.perUserTokensPerSecond;
    const ratio = target ? measured / target : NaN;
    const vsStock = stock > 0 ? measured / stock : NaN;
    const g = grade(ratio);
    const max = Math.max(measured, stock || 0, target || 0, physical || 0);
    const withoutSpec = result.decode.withoutSpeculation;
    const provenance = result.ceiling && result.ceiling.peers > 0
      ? 'calibrated on ' + result.ceiling.peers + ' community run' + (result.ceiling.peers === 1 ? '' : 's') + ' of this stack'
      : 'physics only — no comparable community runs yet';
    const html = '<article class="hr-card" aria-label="' + esc(title) + ' headroom">'
      + '<div class="hr-head"><div><h3>' + esc(title) + '</h3><p class="hr-deploy">' + esc(deployment) + '</p></div>'
      + '<div class="hr-grade" title="' + esc(g.note) + '"><span class="hr-grade-letter">' + esc(g.letter) + '</span><span class="hr-grade-note">' + esc(Number.isFinite(ratio) ? Math.round(ratio * 100) + '% of target' : g.note) + '</span></div></div>'
      + barRow('Measured here', measured, max, 'is-measured', 'tok/s')
      + barRow('Stock software', stock, max, 'is-stock', 'projected')
      + barRow('Tuned-run target', target, max, 'is-target', 'projected')
      + barRow('Physical ceiling', physical, max, 'is-physical', 'projected')
      + '<p class="hr-why">'
      + (Number.isFinite(vsStock) ? '<strong>' + esc(vsStock.toFixed(2)) + '×</strong> the stock-software projection · ' : '')
      + 'projected limiter: <strong>' + esc(limiterText(result)) + '</strong>'
      + (withoutSpec && result.decode.speculationMultiplier ? ' · speculation modeled at ×' + esc(result.decode.speculationMultiplier.toFixed(2)) : '')
      + ' · ' + esc(provenance) + '.</p>'
      + '<p class="hr-links"><a href="' + esc(plannerLink(request)) + '" target="_blank" rel="noopener noreferrer">Open this setup in ML Bottleneck</a></p>'
      + '</article>';
    return { html, result };
  }

  // ---- index.html: headroom cards from the lab tables -------------------
  async function renderHeadroom() {
    const section = document.getElementById('headroom');
    if (!section) return;
    const grid = section.querySelector('[data-headroom-grid]');
    const status = section.querySelector('[data-headroom-status]');
    const rows = Array.from(document.querySelectorAll('tr[data-ml-model]')).filter(
      row => requestFromDataset(row.dataset)
    );
    if (!grid || !rows.length) return;
    let engine;
    try {
      engine = await loadEngine();
    } catch (error) {
      if (status) status.textContent = 'Projections could not be loaded from mlbottleneck.com right now; the measured table above stands on its own.';
      return;
    }
    const cards = [];
    for (const row of rows) {
      const data = row.dataset;
      const numericCells = Array.from(row.querySelectorAll('td.num')).map(cell => parseFloat(cell.textContent)).filter(Number.isFinite);
      const measured = numericCells.length ? numericCells[numericCells.length - 1] : parseFloat(data.mlMeasured);
      if (!Number.isFinite(measured)) continue;
      const label = row.querySelector('th.model');
      let title = data.mlModel;
      if (label) {
        const clone = label.cloneNode(true);
        clone.querySelectorAll('small, .dot, .visually-hidden, .status').forEach(node => node.remove());
        title = clone.textContent.replace(/\s+/g, ' ').trim() || data.mlModel;
      }
      const request = requestFromDataset(data);
      if (!request) continue;
      const card = buildHeadroomCard(engine, request, measured, title, deploymentLabel(data));
      if (card) cards.push(card.html);
    }
    grid.innerHTML = cards.join('');
    if (!cards.length) return;
    if (status) {
      status.textContent = engine.__hasEvidence
        ? 'Projections by the ML Bottleneck physics engine (v' + engine.version + '), calibrated against community benchmark evidence. Grades compare the lab measurement with the projected tuned-run target; they are estimates, not measurements.'
        : 'Projections by the ML Bottleneck physics engine (v' + engine.version + ') without its benchmark evidence (could not be fetched); treat them as uncalibrated estimates.';
    }
    section.hidden = false;
  }

  // ---- index.html: Intel mini-planner -----------------------------------
  const MINI_MODELS = [
    ['qwen3.8_27b', 'Qwen3.8-27B (dense)'],
    ['qwen3.6_35b_a3b', 'Qwen3.6-35B-A3B (MoE)'],
    ['ornith_1.5_35b_a3b', 'Ornith 1.5 35B-A3B (MoE)'],
    ['gemma4_26b_a4b', 'Gemma 4 26B-A4B (MoE)'],
    ['gemma4_31b', 'Gemma 4 31B (dense)'],
    ['muse_glimmer_30b', 'Muse Glimmer 30B'],
    ['minimax_m2.7', 'MiniMax M2.7 (MoE)'],
    ['gpt_oss_120b', 'gpt-oss-120b (MoE)'],
    ['llama3.3_70b', 'Llama 3.3 70B (dense)'],
    ['deepseek_v4_flash', 'DeepSeek V4 Flash (MoE)'],
    ['glm5_2', 'GLM 5.2 (MoE)'],
    ['qwen3.5_122b_a10b', 'Qwen3.5-122B-A10B (MoE)']
  ];
  const MINI_QUANTS = [
    ['Q4_K_M', 'Q4_K_M (llama.cpp)'],
    ['AutoRound INT4', 'INT4 AutoRound / AWQ (vLLM)'],
    ['UD-Q8_K_XL', 'Q8 (llama.cpp)'],
    ['FP8', 'FP8 (vLLM)'],
    ['bfloat16', 'BF16 (uncompressed)']
  ];
  const MINI_HARDWARE = [
    ['Intel Arc Pro B70', 'Intel Arc Pro B70 (32 GB)'],
    ['Intel Arc Pro B65', 'Intel Arc Pro B65 (32 GB)'],
    ['Intel Arc Pro B60', 'Intel Arc Pro B60 (24 GB)'],
    ['Intel Arc B580', 'Intel Arc B580 (12 GB)']
  ];

  function renderMiniPlanner() {
    const root = document.getElementById('mini-planner');
    if (!root) return;
    const form = root.querySelector('form');
    const output = root.querySelector('[data-mini-output]');
    if (!form || !output) return;
    const option = (pairs, selected) => pairs.map(([value, label]) => '<option value="' + esc(value) + '"' + (value === selected ? ' selected' : '') + '>' + esc(label) + '</option>').join('');
    form.innerHTML =
      '<label>Model<select name="model">' + option(MINI_MODELS, 'qwen3.8_27b') + '</select></label>'
      + '<label>Card<select name="hardware">' + option(MINI_HARDWARE, 'Intel Arc Pro B70') + '</select></label>'
      + '<label>Cards<select name="count"><option value="1">1</option><option value="2">2</option><option value="4">4</option></select></label>'
      + '<label>Compression<select name="quant">' + option(MINI_QUANTS, 'Q4_K_M') + '</select></label>'
      + '<label>Software<select name="runtime"><option value="llama_cpp">llama.cpp (SYCL)</option><option value="vllm">vLLM (XPU)</option></select></label>'
      + '<label>Speed-up<select name="spec"><option value="none">none</option><option value="mtp:3">MTP (3 drafts)</option><option value="mtp:5">MTP (5 drafts)</option><option value="dflash:7">DFlash</option><option value="dspark:7">DSpark</option></select></label>'
      + '<label>Prompt tokens<input name="prompt" type="number" min="64" max="131072" step="64" value="1024"></label>'
      + '<label>Concurrent users<input name="batch" type="number" min="1" max="64" step="1" value="1"></label>';
    const update = async () => {
      const data = new FormData(form);
      const request = {
        model: String(data.get('model')),
        hardware: { template: String(data.get('hardware')), count: parseInt(data.get('count'), 10) || 1 },
        quantization: String(data.get('quant')),
        runtime: String(data.get('runtime')),
        speculation: parseSpec(String(data.get('spec'))),
        promptTokens: parseInt(data.get('prompt'), 10) || 1024,
        outputTokens: 512,
        batchSize: parseInt(data.get('batch'), 10) || 1
      };
      output.innerHTML = '<p class="mini-note">Computing…</p>';
      let engine;
      try {
        engine = await loadEngine();
      } catch (error) {
        output.innerHTML = '<p class="mini-note">The prediction engine could not be loaded. <a href="' + esc(plannerLink(request)) + '" target="_blank" rel="noopener noreferrer">Open this setup on mlbottleneck.com</a> instead.</p>';
        return;
      }
      let result;
      try {
        result = engine.predict(request);
      } catch (error) {
        output.innerHTML = '<p class="mini-note">' + esc(error.message) + '</p>';
        return;
      }
      const device = result.devices[0] || {};
      const fit = result.fits
        ? 'Fits: ' + fmt(result.memory.residentWeightsGB) + ' GB weights + ' + fmt(result.memory.kvCacheGB) + ' GB KV of ' + fmt(result.memory.availableGB) + ' GB'
        : (device.overflowMode === 'experts' ? 'Does not fit: MoE experts stream from system RAM' : 'Does not fit: weights spill to system RAM');
      const perUser = result.decode.perUserTokensPerSecond;
      const aggregate = result.decode.tokensPerSecond;
      output.innerHTML =
        '<div class="mini-stats">'
        + '<div><span class="mini-k">Decode</span><span class="mini-v">' + esc(fmt(perUser)) + '</span><span class="mini-u">tok/s per user' + (request.batchSize > 1 ? ' · ' + esc(fmt(aggregate)) + ' combined' : '') + '</span></div>'
        + '<div><span class="mini-k">Prompt processing</span><span class="mini-v">' + esc(fmt(result.prefill.tokensPerSecond)) + '</span><span class="mini-u">tok/s · first token in ' + esc(fmt(result.prefill.timeToFirstTokenSeconds, 1)) + ' s</span></div>'
        + '<div><span class="mini-k">Tuned-run target</span><span class="mini-v">' + esc(fmt(result.ceiling ? result.ceiling.optimizedTokensPerSecond : NaN)) + '</span><span class="mini-u">tok/s · physical ceiling ' + esc(fmt(result.ceiling ? result.ceiling.physicalTokensPerSecond : NaN)) + '</span></div>'
        + '</div>'
        + '<p class="mini-note">' + esc(fit) + ' · limiter: ' + esc(limiterText(result))
        + (result.warnings.length ? ' · ' + esc(result.warnings.join(' ')) : '')
        + ' · ' + (result.ceiling && result.ceiling.peers > 0 ? 'calibrated on ' + result.ceiling.peers + ' community run' + (result.ceiling.peers === 1 ? '' : 's') : 'physics only, no matching community runs') + '.</p>'
        + '<p class="mini-links"><a href="' + esc(plannerLink({ ...request, quantization: request.quantization })) + '" target="_blank" rel="noopener noreferrer">Open the full plan on mlbottleneck.com</a></p>';
    };
    form.addEventListener('change', update);
    form.addEventListener('submit', event => { event.preventDefault(); update(); });
    root.hidden = false;
    update();
  }

  // ---- learn/hardware.html: projected comparison charts -----------------
  const COMPARE_DEVICES = [
    ['Intel Arc Pro B70', 'Arc Pro B70', 'lab'],
    ['Intel Arc Pro B65', 'Arc Pro B65', 'comm'],
    ['Intel Arc Pro B60', 'Arc Pro B60', 'spec'],
    ['AMD Radeon AI PRO R9700', 'Radeon AI PRO R9700', 'spec'],
    ['NVIDIA DGX Spark (GB10)', 'DGX Spark (GB10)', 'spec'],
    ['RTX 4090', 'RTX 4090', 'spec'],
    ['RTX 5090', 'RTX 5090', 'spec'],
    ['Mac M4 Max (128)', 'Mac M4 Max', 'spec'],
    ['AMD Strix Halo (Ryzen AI Max+ 395)', 'Strix Halo 128 GB', 'spec']
  ];
  const COMPARE_WORKLOADS = [
    { key: 'dense', label: 'Qwen3.8-27B · Q4_K_M · 4K prompt', request: { model: 'qwen3.8_27b', quantization: 'Q4_K_M', promptTokens: 4096, outputTokens: 512 } },
    { key: 'moe', label: 'Qwen3.6-35B-A3B · Q4_K_M · 4K prompt', request: { model: 'qwen3.6_35b_a3b', quantization: 'Q4_K_M', promptTokens: 4096, outputTokens: 512 } }
  ];

  function svgBars(rows, title, unit) {
    const width = 640;
    const rowH = 26;
    const left = 190;
    const height = rows.length * rowH + 36;
    const max = Math.max.apply(null, rows.map(r => r.value || 0).concat([1]));
    const body = rows.map((row, index) => {
      const y = 30 + index * rowH;
      const w = Math.max(2, (row.value / max) * (width - left - 90));
      const fill = row.tag === 'lab' ? 'var(--spot)' : (row.tag === 'comm' ? '#8b3b14' : 'var(--ink)');
      return '<text x="' + (left - 8) + '" y="' + (y + 16) + '" text-anchor="end" font-size="12" font-family="var(--mono)" fill="var(--ink)">' + esc(row.label) + '</text>'
        + '<rect x="' + left + '" y="' + (y + 4) + '" width="' + w.toFixed(1) + '" height="16" fill="' + fill + '"' + (row.tag === 'spec' ? ' opacity="0.55"' : '') + '></rect>'
        + '<text x="' + (left + w + 6).toFixed(1) + '" y="' + (y + 16) + '" font-size="12" font-family="var(--mono)" fill="var(--ink)">' + esc(fmt(row.value)) + (row.extra ? ' ' + esc(row.extra) : '') + '</text>';
    }).join('');
    return '<svg viewBox="0 0 ' + width + ' ' + height + '" width="100%" role="img" aria-label="' + esc(title) + '" xmlns="http://www.w3.org/2000/svg">'
      + '<text x="0" y="16" font-size="12" font-weight="700" font-family="var(--mono)" fill="var(--ink)">' + esc(title) + ' (' + esc(unit) + ')</text>' + body + '</svg>';
  }

  async function renderHardwareComparison() {
    const root = document.getElementById('projected-comparison');
    if (!root) return;
    const status = root.querySelector('[data-projection-status]');
    const charts = root.querySelector('[data-projection-charts]');
    if (!charts) return;
    let engine;
    try {
      engine = await loadEngine();
    } catch (error) {
      if (status) status.textContent = 'The projection engine could not be loaded from mlbottleneck.com; the spec table above is unaffected.';
      return;
    }
    const blocks = [];
    for (const workload of COMPARE_WORKLOADS) {
      const rowsDecode = [];
      const rowsPrefill = [];
      const rowsAggregate = [];
      const tableRows = [];
      for (const [template, label, tag] of COMPARE_DEVICES) {
        let single;
        let batched;
        try {
          single = engine.predict({ ...workload.request, hardware: template, runtime: 'auto', batchSize: 1 });
          batched = engine.predict({ ...workload.request, hardware: template, runtime: 'auto', batchSize: 16 });
        } catch (error) {
          continue;
        }
        const fits = single.fits;
        const note = fits ? '' : (single.devices[0] && single.devices[0].overflowMode === 'experts' ? '(experts in RAM)' : '(spills to RAM)');
        rowsDecode.push({ label, value: single.decode.perUserTokensPerSecond, tag, extra: note });
        rowsPrefill.push({ label, value: single.prefill.tokensPerSecond, tag, extra: note });
        rowsAggregate.push({ label, value: batched.decode.tokensPerSecond, tag, extra: note });
        tableRows.push('<tr><td>' + esc(label) + '</td><td class="num">' + esc(fmt(single.decode.perUserTokensPerSecond)) + '</td><td class="num">' + esc(fmt(single.prefill.tokensPerSecond)) + '</td><td class="num">' + esc(fmt(batched.decode.tokensPerSecond)) + '</td><td>' + esc(single.config.runtime) + (fits ? '' : ' · ' + note) + (single.ceiling && single.ceiling.peers ? ' · ' + single.ceiling.peers + ' calibration runs' : '') + '</td></tr>');
      }
      blocks.push(
        '<h3>' + esc(workload.label) + '</h3>'
        + '<figure class="chart">' + svgBars(rowsDecode, 'Decode, one user', 'tok/s') + '</figure>'
        + '<figure class="chart">' + svgBars(rowsPrefill, 'Prompt processing', 'tok/s') + '</figure>'
        + '<figure class="chart">' + svgBars(rowsAggregate, 'Combined throughput, 16 concurrent users', 'tok/s') + '</figure>'
        + '<details class="projection-table"><summary>Numbers as a table</summary><div class="scroller"><table class="data"><thead><tr><th>Card</th><th class="num">Decode tok/s</th><th class="num">Prompt tok/s</th><th class="num">16-user tok/s</th><th>Runtime · notes</th></tr></thead><tbody>' + tableRows.join('') + '</tbody></table></div></details>'
      );
    }
    charts.innerHTML = blocks.join('');
    if (status) {
      status.innerHTML = 'Projected by the <a class="inline" href="https://mlbottleneck.com/" target="_blank" rel="noopener noreferrer">ML Bottleneck</a> physics engine v' + esc(engine.version)
        + (engine.__hasEvidence ? ', calibrated against community benchmark runs' : ' (benchmark evidence unavailable, uncalibrated)')
        + '. Blue = this lab has measured the card; brown = community-reported; grey = vendor spec only. Each card runs its usual software (llama.cpp on Intel/AMD/GeForce, MLX on Mac). These are estimates to compare with, not numbers to quote.';
    }
    root.hidden = false;
  }

  function svgLine(points, title, unit, xLabel) {
    const width = 640, height = 250, left = 64, top = 22, right = 20, bottom = 44;
    const xs = points.map(p => Math.max(1, p.x));
    const ys = points.map(p => p.y);
    const lx = xs.map(x => Math.log2(x));
    const x0 = Math.min.apply(null, lx), x1 = Math.max.apply(null, lx);
    const yMax = Math.max.apply(null, ys.concat([1])) * 1.1;
    const sx = x => left + ((Math.log2(Math.max(1, x)) - x0) / Math.max(1e-9, x1 - x0)) * (width - left - right);
    const sy = y => top + (1 - y / yMax) * (height - top - bottom);
    const path = points.map((p, i) => (i ? 'L' : 'M') + sx(p.x).toFixed(1) + ',' + sy(p.y).toFixed(1)).join(' ');
    const dots = points.map(p => '<circle cx="' + sx(p.x).toFixed(1) + '" cy="' + sy(p.y).toFixed(1) + '" r="3.5" fill="var(--ink)"></circle>'
      + '<text x="' + sx(p.x).toFixed(1) + '" y="' + (sy(p.y) - 8).toFixed(1) + '" text-anchor="middle" font-size="11" font-family="var(--mono)" fill="var(--ink)">' + esc(fmt(p.y)) + '</text>'
      + '<text x="' + sx(p.x).toFixed(1) + '" y="' + (height - 24) + '" text-anchor="middle" font-size="11" font-family="var(--mono)" fill="var(--muted)">' + esc(p.label) + '</text>').join('');
    return '<svg viewBox="0 0 ' + width + ' ' + height + '" width="100%" role="img" aria-label="' + esc(title) + '" xmlns="http://www.w3.org/2000/svg">'
      + '<text x="0" y="14" font-size="12" font-weight="700" font-family="var(--mono)" fill="var(--ink)">' + esc(title) + ' (' + esc(unit) + ')</text>'
      + '<line x1="' + left + '" y1="' + sy(0).toFixed(1) + '" x2="' + (width - right) + '" y2="' + sy(0).toFixed(1) + '" stroke="var(--ink)" stroke-width="2"></line>'
      + '<path d="' + path + '" fill="none" stroke="var(--ink)" stroke-width="2.5" stroke-dasharray="6 4"></path>' + dots
      + '<text x="' + left + '" y="' + (height - 6) + '" font-size="11" font-family="var(--mono)" fill="var(--muted)">' + esc(xLabel) + '</text></svg>';
  }

  const kTokens = value => value >= 1024 ? (value / 1024).toFixed(value % 1024 ? 1 : 0) + 'K' : String(value);

  // ---- models/<id>.html: package projection card + projected scaling ----
  async function renderPackagePage() {
    const root = document.getElementById('package-page');
    const block = document.getElementById('package-projection');
    if (!root || !block || !root.dataset.mlModel) return;
    const status = block.querySelector('[data-projection-status]');
    const cardHost = block.querySelector('[data-package-card]');
    const charts = block.querySelector('[data-package-charts]');
    let engine;
    try {
      engine = await loadEngine();
    } catch (error) {
      if (status) status.textContent = 'Projections could not be loaded from mlbottleneck.com right now; the measured numbers above stand on their own.';
      return;
    }
    const data = root.dataset;
    const measured = parseFloat(data.mlMeasured);
    const request = requestFromDataset(data);
    if (!request) return;
    const title = (document.querySelector('header.hero h1') || {}).textContent || data.mlModel;
    const card = buildHeadroomCard(engine, request, measured, title.trim(), deploymentLabel(data));
    if (!card) {
      if (status) status.textContent = 'This package could not be projected (unknown preset or quantization).';
      return;
    }
    cardHost.innerHTML = card.html;
    try {
      const sweep = engine.sweep(request, { levels: [1, 2, 4, 8, 16, 32] });
      const ctxPoints = sweep.context.points.filter(p => p.decodeTokS > 0).map(p => ({ x: p.promptTokens, y: p.expectedDecodeTokS || p.decodeTokS, label: kTokens(p.promptTokens) }));
      const userPoints = sweep.concurrency.points.filter(p => p.fits !== false).map(p => {
        const users = p.concurrency || p.users || p.batchSize || 1;
        const aggregate = p.expectedAggregateTokS || p.aggregateTokS || ((p.expectedPerUserTokS || p.perUserTokS || 0) * users);
        return { x: users, y: aggregate, label: String(users) };
      });
      charts.innerHTML = '<figure class="chart">' + svgLine(ctxPoints, 'Projected decode vs input length (stock software)', 'tok/s', 'prompt tokens · dashed = projection') + '</figure>'
        + (userPoints.length > 1 ? '<figure class="chart">' + svgLine(userPoints, 'Projected combined throughput vs concurrent users', 'tok/s', 'concurrent users · dashed = projection') + '</figure>' : '');
    } catch (error) {
      charts.innerHTML = '';
    }
    if (status) {
      status.textContent = 'Projected by the ML Bottleneck physics engine v' + engine.version
        + (engine.__hasEvidence ? ', calibrated against community benchmark evidence' : ' without its benchmark evidence (uncalibrated)')
        + '. The lab measurement above is the only measured number here; the stock projection, tuned-run target, ceiling, and curves are estimates.';
    }
    block.hidden = false;
  }

  // ---- models/<family>.html: compact projected optimization grades ------
  async function renderFamilyHeadroomGrades() {
    const cards = Array.from(document.querySelectorAll('[data-family-headroom]'));
    if (!cards.length) return;
    let engine;
    try {
      engine = await loadEngine();
    } catch (error) {
      return; // Static evidence and packet maturity remain visible.
    }
    for (const card of cards) {
      const measured = parseFloat(card.dataset.mlMeasured);
      const badge = card.querySelector('[data-family-headroom-value]');
      if (!badge || !Number.isFinite(measured)) continue;
      const request = requestFromDataset(card.dataset);
      if (!request) {
        badge.textContent = 'OPT —';
        continue;
      }
      try {
        const result = engine.predict(request);
        const target = result.ceiling && result.ceiling.optimizedTokensPerSecond;
        const g = grade(target > 0 ? measured / target : NaN);
        badge.textContent = 'OPT ' + g.letter;
        badge.title = 'Projected optimization headroom: ' + g.note
          + (target > 0 ? ' · measured ' + fmt(measured) + ' / projected tuned target ' + fmt(target) + ' tok/s' : '')
          + '. This is not model quality or packet evidence.';
        badge.dataset.ready = 'true';
      } catch (error) {
        badge.textContent = 'OPT —';
      }
    }
  }

  function boot() {
    renderHeadroom();
    renderMiniPlanner();
    renderHardwareComparison();
    renderPackagePage();
    renderFamilyHeadroomGrades();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
