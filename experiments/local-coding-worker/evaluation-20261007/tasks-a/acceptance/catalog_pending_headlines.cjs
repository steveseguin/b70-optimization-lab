const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('guides.html', 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x => x[1]).find(x => x.includes('packages/catalog.json'));
assert(script, 'Catalog UI not found');
const catalog = JSON.parse(fs.readFileSync('packages/catalog.json', 'utf8'));
const seed = catalog.packages[0];
function item(id, speed) {
 const row = structuredClone(seed); row.id = id; row.name = id;
 row.library.featured_metric = speed === null ? null : {value:speed,unit:'tok/s',scope:'Fixture scope'};
 row.library.benchmark_status = 'Unmeasured <status> & pending'; return row;
}
const data = {...catalog,packages:[item('pending-z',null),item('slow',20),item('fast-b',40),item('fast-a',40),item('pending-a',null)]};
delete data.packages[4].library.featured_metric;
const nodes = Object.fromEntries(['search','cards','quant','os','delivery','status','sort','package-grid','result-count','catalog-summary','reset'].map(id => [id,{
 id,name:id,value:id === 'sort' ? 'newest' : '',tagName:id === 'search' ? 'INPUT' : 'SELECT',options:[],events:{},
 addEventListener(name,fn){this.events[name]=fn;},appendChild(x){this.options.push(x);}
}]));
const errors=[];
vm.runInNewContext(script, {document:{getElementById:id=>nodes[id],createElement:()=>({})},
 fetch:async()=>({ok:true,json:async()=>data}),console:{error:x=>errors.push(String(x))},URLSearchParams,
 location:{pathname:'/guides.html',search:''},history:{replaceState(){}},navigator:{},window:{setTimeout}});
setImmediate(() => {
 try {
  assert.equal(errors.length,0,'PENDING_HEADLINE_FAILURE: a valid package without a headline must not break the catalog');
  const ids=()=>[...nodes['package-grid'].innerHTML.matchAll(/data-id="([^"]+)"/g)].map(x=>x[1]);
  assert.equal(ids().length,5);
  assert.equal((nodes['package-grid'].innerHTML.match(/Strict headline pending/g)||[]).length,2);
  assert(nodes['package-grid'].innerHTML.includes('Unmeasured &lt;status&gt; &amp; pending'));
  assert(!nodes['package-grid'].innerHTML.includes('NaN'));
  nodes.sort.value='speed';nodes.sort.events.change();
  assert.deepEqual(ids(),['fast-a','fast-b','slow','pending-a','pending-z'],'Measured speed order and deterministic pending/tie ordering');
  for(const order of ['cards','name','newest']){nodes.sort.value=order;nodes.sort.events.change();assert.equal(ids().length,5);}
  nodes.search.value='nonexistent-fixture';nodes.search.events.input();assert.equal(ids().length,0);
  nodes.reset.events.click();assert.equal(ids().length,5);
  console.log('PASS: null/absent headlines, escaped status, speed/tie order and UI filtering');
 } catch(error) {console.error(error.stack);process.exitCode=1;}
});
