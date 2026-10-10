// Execute the actual inline catalog UI without network or browser dependencies.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'guides.html'), 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
  .map(match => match[1]).find(source => source.includes('packages/catalog.json'));
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'packages/catalog.json')));

async function load(data = catalog, ok = true) {
  const elements = {}, errors = [];
  for (const id of ['search', 'cards', 'quant', 'os', 'delivery', 'status', 'sort',
                    'package-grid', 'result-count', 'catalog-summary', 'reset']) {
    elements[id] = {id, name: id, value: id === 'sort' ? 'newest' : '',
      tagName: id === 'search' ? 'INPUT' : 'SELECT', options: [], events: {},
      addEventListener(event, fn) { this.events[event] = fn; },
      appendChild(option) { this.options.push(option); }};
  }
  const context = {document: {getElementById: id => elements[id], createElement: () => ({})},
    fetch: async () => ({ok, status: 503, json: async () => data}),
    console: {error: error => errors.push(error)}, URLSearchParams,
    location: {pathname: '/guides.html', search: ''}, history: {replaceState() {}},
    navigator: {}, window: {setTimeout}};
  vm.runInNewContext(script, context);
  await new Promise(setImmediate);
  return {elements, errors};
}
const ids = page => [...page.elements['package-grid'].innerHTML.matchAll(/data-id="([^"]+)"/g)].map(m => m[1]);

test('real catalog renders; every sort/filter and reset handles pending headlines', async () => {
  const page = await load();
  assert.equal(page.errors.length, 0);
  assert.equal(ids(page).length, catalog.packages.length);
  for (const sort of ['newest', 'speed', 'name', 'cards']) {
    page.elements.sort.value = sort;
    page.elements.sort.events.change();
    assert.equal(ids(page).length, catalog.packages.length);
    if (sort === 'speed') {
      let pending = false;
      for (const id of ids(page)) {
        const metric = catalog.packages.find(item => item.id === id).library.featured_metric;
        if (!metric) pending = true;
        else assert.equal(pending, false, 'pending headlines must sort last');
      }
    }
  }
  for (const id of ['cards', 'quant', 'os', 'delivery']) {
    page.elements[id].value = String(page.elements[id].options[0].value);
    page.elements[id].events.change();
    assert.ok(ids(page).length > 0);
    page.elements.reset.events.click();
  }
  page.elements.search.value = 'no-such-model-xyz';
  page.elements.search.events.input();
  assert.match(page.elements['package-grid'].innerHTML, /No package matches/);
  page.elements.reset.events.click();
  assert.equal(ids(page).length, catalog.packages.length);
});

test('null and absent metrics show escaped pending status, not fabricated speeds', async () => {
  const data = structuredClone(catalog);
  data.packages = data.packages.slice(0, 2);
  data.packages[0].library.featured_metric = null;
  delete data.packages[1].library.featured_metric;
  data.packages[0].library.benchmark_status = '<script>bad</script>';
  const page = await load(data);
  assert.equal(page.errors.length, 0);
  assert.equal(ids(page).length, 2);
  assert.equal((page.elements['package-grid'].innerHTML.match(/Benchmark pending/g) || []).length, 2);
  assert.match(page.elements['package-grid'].innerHTML, /&lt;script&gt;bad&lt;\/script&gt;/);
  page.elements.sort.value = 'speed';
  assert.doesNotThrow(() => page.elements.sort.events.change());
});

test('real fetch failures retain the GitHub fallback', async () => {
  const page = await load(catalog, false);
  assert.equal(page.elements['result-count'].textContent, 'Catalog unavailable');
  assert.match(page.elements['package-grid'].innerHTML, /Browse packages on GitHub/);
});

test('cards keep evidence intact but collapsed, with short everyday summaries', async () => {
  const page = await load();
  const cards = [...page.elements['package-grid'].innerHTML.matchAll(/<article\b[\s\S]*?<\/article>/g)];
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  for (const [card] of cards) {
    const item = catalog.packages.find(p => card.includes(`data-id="${p.id}"`));
    const visible = card.replace(/<details\b[\s\S]*?<\/details>/g, '');
    assert.doesNotMatch(card, /<details[^>]*\bopen\b/);
    assert.ok(card.includes(escape(item.library.summary)));
    assert.ok(!visible.includes(escape(item.library.summary)));
    if (item.library.featured_metric) {
      assert.ok(card.includes(escape(item.library.featured_metric.scope)));
      assert.ok(!visible.includes(escape(item.library.featured_metric.scope)));
    }
    for (const person of item.contributors) assert.ok(card.includes(escape(person.contribution)));
    for (const limitation of item.missing) assert.ok(card.includes(escape(limitation)));
    assert.ok(visible.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').length < 700, item.id);
    assert.match(visible, /View setup/);
    if (item.status === 'candidate') assert.match(visible, /Needs testing/);
  }
});


// The bridge must carry the same concurrency into the full planner. These
// tests run its complete script with an offline SDK and DOM boundary.
async function loadMiniPlanner({ failLoad = false, headroom = false } = {}) {
  const bridge = fs.readFileSync(path.join(root, 'learn/assets/mlbottleneck-bridge.js'), 'utf8');
  const events = {}, requests = [];
  const values = {model: 'qwen3.8_27b', hardware: 'Intel Arc Pro B70', count: '1',
    quant: 'Q4_K_M', runtime: 'llama_cpp', spec: 'none', prompt: '1024', batch: '1'};
  const form = {innerHTML: '', addEventListener: (type, handler) => { events[type] = handler; }};
  const output = {innerHTML: ''}, grid = {innerHTML: ''}, status = {};
  const mini = {hidden: true, querySelector: selector => selector === 'form' ? form : output};
  const head = {hidden: true, querySelector: selector => selector === '[data-headroom-grid]' ? grid : status};
  const row = {dataset: {mlModel: values.model, mlHardware: values.hardware, mlCards: '1',
    mlQuant: values.quant, mlRuntime: values.runtime, mlPrompt: '128', mlOutput: '128'},
    querySelectorAll: () => [{textContent: '1'}, {textContent: '30'}], querySelector: () => null};
  const engine = {version: 'offline-test', predict(request) {
    requests.push(request);
    return {devices: [{}], fits: true, memory: {residentWeightsGB: 16, kvCacheGB: 1, availableGB: 32},
      decode: {perUserTokensPerSecond: 20, tokensPerSecond: 20 * (request.batchSize || 1)},
      prefill: {tokensPerSecond: 1000, timeToFirstTokenSeconds: 1},
      ceiling: {optimizedTokensPerSecond: 25, physicalTokensPerSecond: 30, peers: 0}, warnings: []};
  }};
  const context = {URLSearchParams, window: {MLBottleneck: {createEngine: () => engine}},
    FormData: class {get(key) {return values[key];}},
    fetch: async () => ({ok: false}), document: {readyState: 'complete',
      getElementById: id => id === 'mini-planner' ? mini : headroom && id === 'headroom' ? head : null,
      querySelectorAll: selector => headroom && selector === 'tr[data-ml-model]' ? [row] : [],
      createElement: () => ({}), head: {appendChild: script => script.onerror()}}};
  if (failLoad) delete context.window.MLBottleneck;
  vm.runInNewContext(bridge, context);
  await new Promise(setImmediate);
  return {values, form, output, grid, mini, requests, async update() {await events.change();},
    async submit() {await events.submit({preventDefault() {}}); await new Promise(setImmediate);}};
}
function linkedPlan(html) {
  const link = html.match(/href="([^"]+)"/);
  assert.ok(link, 'the full-plan link is present');
  return new URL(link[1].replaceAll('&amp;', '&'));
}

test('mini-planner retains arbitrary integer concurrency in its original range', async () => {
  const page = await loadMiniPlanner();
  assert.match(page.form.innerHTML, /<input name="batch" type="number" min="1" max="64" step="1" value="1">/);
  assert.equal(page.mini.hidden, false);
});
for (const batch of [1, 2, 4, 8, 16, 32, 64]) {
  test(`mini-planner full-plan link preserves ${batch} concurrent users`, async () => {
    const page = await loadMiniPlanner();
    page.values.batch = String(batch);
    await page.update();
    assert.equal(page.requests.at(-1).batchSize, batch);
    const link = linkedPlan(page.output.innerHTML);
    assert.equal(link.searchParams.get('batch'), String(batch));
    assert.equal(link.searchParams.get('model'), page.values.model);
    assert.equal(link.searchParams.get('hardware'), page.values.hardware);
    assert.equal(link.searchParams.get('format'), page.values.quant);
    assert.equal(link.searchParams.get('runtime'), page.values.runtime);
    assert.equal(link.searchParams.get('prompt'), '1024');
    assert.equal(link.searchParams.get('output'), '512');
    assert.equal(link.hash, '#plan');
  });
}

test('repeated changes and submit carry the latest count alongside speculation and cards', async () => {
  const page = await loadMiniPlanner();
  Object.assign(page.values, {batch: '64', spec: 'mtp:5', count: '4', prompt: '4096'});
  await page.update();
  page.values.batch = '2';
  await page.submit();
  const params = linkedPlan(page.output.innerHTML).searchParams;
  assert.equal(params.get('batch'), '2');
  assert.equal(params.get('count'), '4');
  assert.equal(params.get('spec'), 'mtp:5');
  assert.equal(params.get('prompt'), '4096');
});

test('SDK load failure fallback carries the same selected concurrent count', async () => {
  const page = await loadMiniPlanner({failLoad: true});
  page.values.batch = '32';
  await page.update();
  assert.match(page.output.innerHTML, /could not be loaded/);
  assert.equal(linkedPlan(page.output.innerHTML).searchParams.get('batch'), '32');
  assert.equal(page.requests.length, 0);
});

test('single-user headroom links explicitly reset concurrency to one', async () => {
  const page = await loadMiniPlanner({headroom: true});
  assert.equal(linkedPlan(page.grid.innerHTML).searchParams.get('batch'), '1');
  assert.equal(page.requests.find(request => request.promptTokens === 128).batchSize, undefined);
});

for (const batch of [3, 5, 63]) {
  test(`unsupported full-plan count ${batch} keeps its local projection without a misleading link`, async () => {
    const page = await loadMiniPlanner();
    page.values.batch = String(batch);
    await page.update();
    assert.equal(page.requests.at(-1).batchSize, batch);
    assert.match(page.output.innerHTML, /tok\/s per user/);
    assert.match(page.output.innerHTML, new RegExp(`cannot import ${batch} concurrent users`));
    assert.doesNotMatch(page.output.innerHTML, /href=/);
    page.values.batch = '16';
    await page.update();
    assert.equal(linkedPlan(page.output.innerHTML).searchParams.get('batch'), '16');
    page.values.batch = String(batch);
    await page.update();
    assert.doesNotMatch(page.output.innerHTML, /href=/);
  });
}
test('SDK failure cannot create a misleading link for unsupported concurrency', async () => {
  const page = await loadMiniPlanner({failLoad: true});
  page.values.batch = '3';
  await page.update();
  assert.match(page.output.innerHTML, /could not be loaded/);
  assert.match(page.output.innerHTML, /cannot import 3 concurrent users/);
  assert.doesNotMatch(page.output.innerHTML, /href=/);
});
