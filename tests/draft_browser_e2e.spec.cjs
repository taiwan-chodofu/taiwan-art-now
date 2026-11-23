const { test, expect } = require('@playwright/test');
const path = require('node:path');

async function boot(page) {
  await page.goto('http://127.0.0.1:8765/tests/draft_browser_fixture.html');
  await page.evaluate(() => {
    localStorage.removeItem('taiwan_art_favs');
    localStorage.removeItem('taiwan_art_visited');
    document.body.innerHTML = '<button id="fav">観たい</button><button id="visited">観た</button><p id="status"></p>';
  });
  for (const name of ['draft_legacy_snapshot.js', 'draft_legacy_writer.js', 'draft_action_commit.js']) {
    await page.addScriptTag({ path: path.resolve(__dirname, '../static/js', name) });
  }
  await page.evaluate(() => {
    window._uiEvents = [];
    const adapter = TanDraftActionCommit.create({
      storage: localStorage, locks: navigator.locks,
      onCommitted({kind, action}) {
        document.getElementById('status').textContent = kind + ':' + action;
        window._uiEvents.push('committed');
      },
      onFailure(result) {
        document.getElementById('status').textContent = 'error:' + result.status;
        window._uiEvents.push('failed');
      },
      onBusy(busy) { document.querySelectorAll('button').forEach(b => b.disabled = busy); }
    });
    const fav = {title:'台南展覽',museum:'Museum',dates:'2026',url:'/e/a',region:'臺南',event:''};
    const visited = {date:'2026-11-23T01:02:03.000Z',title:'台南展覽',museum:'Museum',dates:'2026',url:'/e/a',region:'臺南'};
    document.getElementById('fav').onclick = async () => {
      const exists = JSON.parse(localStorage.getItem('taiwan_art_favs') || '{}').a;
      await adapter.commit({kind:'favs',key:'a',action:exists?'remove':'set',value:fav});
    };
    document.getElementById('visited').onclick = async () => {
      const exists = JSON.parse(localStorage.getItem('taiwan_art_visited') || '{}').a;
      await adapter.commit({kind:'visited',key:'a',action:exists?'remove':'set',value:visited});
    };
  });
}
test('real Chromium: favorite add/remove persists and UI follows write', async ({page}) => {
  await boot(page);
  await page.locator('#fav').click();
  await expect(page.locator('#status')).toHaveText('favs:set');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('taiwan_art_favs')).a.title)).toBe('台南展覽');
  await page.locator('#fav').click();
  await expect(page.locator('#status')).toHaveText('favs:remove');
  expect(await page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))))).toEqual([]);
});
test('real Chromium: visited object add/remove independent from favorites', async ({page}) => {
  await boot(page);
  await page.locator('#fav').click();
  await page.locator('#visited').click();
  await expect(page.locator('#status')).toHaveText('visited:set');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('taiwan_art_visited')).a.date)).toBe('2026-11-23T01:02:03.000Z');
  await page.locator('#visited').click();
  await expect(page.locator('#status')).toHaveText('visited:remove');
  expect(await page.evaluate(() => Boolean(JSON.parse(localStorage.getItem('taiwan_art_favs')).a))).toBe(true);
});
test('real Chromium: storage failure never displays saved success', async ({page}) => {
  await boot(page);
  await page.evaluate(() => {
    const proto = Storage.prototype;
    const original = proto.setItem;
    proto.setItem = function(k,v) {
      if (k === 'taiwan_art_favs') throw new DOMException('quota','QuotaExceededError');
      return original.call(this,k,v);
    };
  });
  await page.locator('#fav').click();
  await expect(page.locator('#status')).toHaveText('error:unavailable');
  expect(await page.evaluate(() => localStorage.getItem('taiwan_art_favs'))).toBeNull();
  expect(await page.evaluate(() => window._uiEvents)).toEqual(['failed']);
});
test('real Chromium: two tabs serialize independent favorite additions', async ({browser}) => {
  const context = await browser.newContext();
  try {
    const a = await context.newPage(), b = await context.newPage();
    await boot(a); await boot(b);
    await Promise.all([
      a.evaluate(() => TanDraftActionCommit.create({storage:localStorage,locks:navigator.locks,onCommitted(){},onFailure(){}}).commit({kind:'favs',key:'one',action:'set',value:{title:'One',museum:'M'}})),
      b.evaluate(() => TanDraftActionCommit.create({storage:localStorage,locks:navigator.locks,onCommitted(){},onFailure(){}}).commit({kind:'favs',key:'two',action:'set',value:{title:'Two',museum:'M'}}))
    ]);
    const keys = await a.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))).sort());
    expect(keys).toEqual(['one','two']);
  } finally { await context.close(); }
});

test('legacy cached tab bypassing Web Locks can still overwrite newer data (known blocker)', async ({browser}) => {
  const context = await browser.newContext();
  try {
    const modern = await context.newPage(), legacy = await context.newPage();
    await boot(modern); await boot(legacy);
    // Cached old code snapshots the whole map without taking the shared lock.
    const stale = await legacy.evaluate(() => localStorage.getItem('taiwan_art_favs') || '{}');
    const result = await modern.evaluate(() => TanDraftActionCommit.create({
      storage: localStorage, locks: navigator.locks,
      onCommitted(){}, onFailure(){}
    }).commit({kind:'favs',key:'newer',action:'set',value:{title:'Newer',museum:'M'}}));
    expect(result.status).toBe('written_under_cooperative_lock');
    await legacy.evaluate(raw => {
      const map = JSON.parse(raw);
      map.older = {title:'Older',museum:'M'};
      localStorage.setItem('taiwan_art_favs', JSON.stringify(map));
    }, stale);
    const keys = await modern.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('taiwan_art_favs'))));
    // This intentionally documents the unresolved unsafe old-tab behavior.
    expect(keys).toEqual(['older']);
  } finally { await context.close(); }
});
