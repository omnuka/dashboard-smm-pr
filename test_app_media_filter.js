const assert = require('node:assert/strict');
const { isMediaOrSite, brandNames, isCompetitorFinding, state } = require('./app.js');

state.competitors = [{ name: 'Depot', site: 'https://depotwpf.ru' }];

const mediaFinding = {
  source_type: 'СМИ',
  channel: 'СМИ',
  media_source: 'Sostav',
  placement: 'Sostav',
  competitor: 'Depot',
  monitor_scope: 'competitor',
  date: '2026-06-25',
  title: 'Тестовое СМИ-упоминание',
  url: 'https://example.com/media-item'
};
const clientScopedFinding = {
  source_type: 'СМИ',
  channel: 'СМИ',
  media_source: 'Sostav',
  competitor: 'Клиенты Serenity',
  monitor_scope: 'client_brand',
  client_brands: [{ name: 'Не должен попасть' }],
  url: 'https://example.com/client-brand'
};

assert.equal([mediaFinding].filter(isMediaOrSite).length, 1);
assert.equal(isMediaOrSite(mediaFinding), true);
assert.equal(isCompetitorFinding(mediaFinding), true);
assert.equal(isCompetitorFinding(clientScopedFinding), false);
assert.deepEqual(brandNames(clientScopedFinding), []);
