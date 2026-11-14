/* Verify browser launcher manifest validation with synthetic OPFS entries. */
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const site = path.resolve(__dirname, '../site');
const map = Buffer.alloc(256);
map.write('MPQ', 0); map[3] = 0x1a;
map.writeUInt32LE(32, 4); map.writeUInt32LE(256, 8);
map.writeUInt32LE(32, 16); map.writeUInt32LE(48, 20);
map.writeUInt32LE(1, 24); map.writeUInt32LE(1, 28);
const mpq = Buffer.from(map.subarray(0, 64));
mpq.writeUInt32LE(64, 8);
function dir(entries) {
  return {
    async getDirectoryHandle(name) {
      const value = entries[name];
      if (!value || typeof value.getDirectoryHandle !== 'function') {
        const error = new Error('Missing directory ' + name);
        error.name = 'NotFoundError';
        throw error;
      }
      return value;
    },
    async getFileHandle(name) {
      const value = entries[name];
      if (!(value instanceof Blob)) throw new Error('Missing file ' + name);
      return {getFile: async () => value};
    }
  };
}
async function launch(mapPath, {corruptBase = false, edition, completeness, expansion = false,
  requested = null, startResult = true, customMaps = false, badMap = false} = {}) {
  const manifest = {
    version:3, generation:'install-abcd-1234',
    ...(edition ? {edition, completeness} : {}),
    files:[{name:'War3.mpq', size:mpq.length}, {name:mapPath, size:map.length},
      ...(expansion ? [{name:'War3x.mpq',size:mpq.length}] : [])],
    bytes:mpq.length + map.length + (expansion ? mpq.length : 0)
  };
  const broken = Buffer.from(mpq);
  if (corruptBase) broken.writeUInt32LE(1024, 8);
  const stage = dir({'War3.mpq':new Blob([corruptBase ? broken : mpq]),
    ...(expansion ? {'War3x.mpq':new Blob([mpq])} : {}), 'Maps':dir({
    '(4)LostTemple.w3m':new Blob([map])
  })});
  const extraMap = badMap ? new Blob([Buffer.alloc(96)]) : new Blob([map]);
  const libraryManifest = {version:1, generation:'maps-abcd-1234',
    files:[{name:'Maps/Download/Custom.w3x', size:extraMap.size}], bytes:extraMap.size};
  const store = dir({openrealm:dir({'game-data':dir({wc3:dir({
    'installation.json':new Blob([JSON.stringify(manifest)]),
    'install-abcd-1234':stage,
    ...(customMaps ? {'map-library':dir({
      'maps.json':new Blob([JSON.stringify(libraryManifest)]),
      'maps-abcd-1234':dir({'Maps':dir({'Download':dir({'Custom.w3x':extraMap})})})
    })} : {})
  })})})});
  const starts = [];
  const lockRequests = [];
  const activeLocks = new Set();
  const status = {textContent:''};
  const selector = {value:'roc',disabled:true,handlers:{},addEventListener(name,fn){this.handlers[name]=fn;}};
  const session = new Map(requested ? [['openrealm-wc3-browser-mode',requested]] : []);
  let reloads = 0;
  const context = vm.createContext({
    navigator:{storage:{getDirectory:async () => store}, locks:{
      request:async (name, options, callback) => {
        lockRequests.push([name, options.mode]);
        activeLocks.add(name);
        try { return await callback({name, mode:options.mode}); }
        finally { activeLocks.delete(name); }
      }
    }},
    document:{getElementById:id => id === 'game-edition' ? selector : status},
    sessionStorage:{getItem:key=>session.get(key) ?? null,setItem:(key,value)=>session.set(key,value)},
    location:{reload:()=>{reloads++;}},
    window:{openrealmStartEngine:args => { starts.push(args); return startResult; },
      openrealmPagesReady:Promise.resolve(true), MPQHeader:require('../site/mpq-header.js')},
    Uint8Array, Number, DataView
  });
  vm.runInContext(fs.readFileSync(path.join(site, 'filesystem-bridge.js'), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  return {starts, status, lockRequests, activeLocks, selector, session, get reloads(){return reloads;}};
}
test('launcher accepts a validated version-3 map under Maps/', async () => {
  const {starts, status} = await launch('Maps/(4)LostTemple.w3m');
  assert.equal(starts.length, 1);
  assert.equal(starts[0][0], '+openrealm-data=/opfs/openrealm/game-data/wc3/install-abcd-1234');
  assert.match(status.textContent, /Validated/);
});
test('launcher rejects path traversal in a version-3 manifest', async () => {
  const {starts, status} = await launch('Maps/../(4)LostTemple.w3m');
  assert.equal(starts.length, 0);
  assert.match(status.textContent, /Invalid archive manifest entry/);
});

test('launcher holds a shared commit lock and generation lease while starting', async () => {
  const {starts, lockRequests, activeLocks} = await launch('Maps/(4)LostTemple.w3m');
  assert.equal(starts.length, 1);
  assert.deepEqual(lockRequests, [
    ['openrealm-wc3-installation', 'shared'],
    ['openrealm-wc3-generation:install-abcd-1234', 'shared']
  ]);
  assert.deepEqual(Array.from(activeLocks), ['openrealm-wc3-generation:install-abcd-1234']);
});

test('failed isolated startup releases the generation lease', async () => {
  const result = await launch('Maps/(4)LostTemple.w3m', {startResult:false});
  assert.equal(result.starts.length, 1);
  assert.equal(result.activeLocks.size, 0);
  assert.match(result.status.textContent, /Browser support or cross-origin isolation is unavailable/);
});

test('launcher rejects corrupt MPQ declared length before engine startup', async () => {
  const {starts, status} = await launch('Maps/(4)LostTemple.w3m', {corruptBase:true});
  assert.equal(starts.length, 0);
  assert.match(status.textContent, /Invalid MPQ archive War3.mpq/);
});


test('launcher accepts and visibly identifies a stored demo edition', async () => {
  const {starts, status} = await launch('Maps/(4)LostTemple.w3m',
    {edition:'demo', completeness:'demo'});
  assert.equal(starts.length, 1);
  assert.match(status.textContent, /Warcraft III Demo installation/);
});

test('launcher refuses contradictory demo edition metadata', async () => {
  const {starts, status} = await launch('Maps/(4)LostTemple.w3m',
    {edition:'demo', completeness:'expansion'});
  assert.equal(starts.length, 0);
  assert.match(status.textContent, /Invalid demo installation manifest/);
});


test('RoC is the default even with expansion archives installed', async () => {
  const result = await launch('Maps/(4)LostTemple.w3m', {expansion:true});
  assert.equal(result.selector.disabled, false);
  assert.equal(result.selector.value, 'roc');
  assert.deepEqual(Array.from(result.starts[0].slice(-3)), ['+set','fs_expansion','0']);
});

test('TFT selection passes expansion mode on next page launch', async () => {
  const result = await launch('Maps/(4)LostTemple.w3m',
    {expansion:true, requested:'tft'});
  assert.equal(result.selector.value, 'tft');
  assert.deepEqual(Array.from(result.starts[0].slice(-3)), ['+set','fs_expansion','1']);
  result.selector.value = 'roc';
  result.selector.handlers.change();
  assert.equal(result.session.get('openrealm-wc3-browser-mode'), 'roc');
  assert.equal(result.reloads, 1);
});

test('TFT preference falls back safely for a base-only install', async () => {
  const result = await launch('Maps/(4)LostTemple.w3m', {requested:'tft'});
  assert.equal(result.selector.disabled, true);
  assert.equal(result.selector.value, 'roc');
  assert.deepEqual(Array.from(result.starts[0].slice(-3)), ['+set','fs_expansion','0']);
});


test('separate map library mounts via extra_data and holds a map generation lease', async () => {
  const result = await launch('Maps/(4)LostTemple.w3m', {customMaps:true});
  assert.equal(result.starts.length, 1);
  assert.deepEqual(Array.from(result.starts[0].slice(1, 4)), ['+set', 'extra_data',
    '/opfs/openrealm/game-data/wc3/map-library/maps-abcd-1234']);
  assert.deepEqual(result.lockRequests, [
    ['openrealm-wc3-installation', 'shared'],
    ['openrealm-wc3-generation:install-abcd-1234', 'shared'],
    ['openrealm-wc3-map-generation:maps-abcd-1234', 'shared']
  ]);
  assert.ok(result.activeLocks.has('openrealm-wc3-map-generation:maps-abcd-1234'));
});

test('corrupt custom map is rejected before engine startup', async () => {
  const result = await launch('Maps/(4)LostTemple.w3m', {customMaps:true, badMap:true});
  assert.equal(result.starts.length, 0);
  assert.match(result.status.textContent, /Invalid imported map/);
});
