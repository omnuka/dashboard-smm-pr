const assert = require('node:assert/strict');
const { isMediaOrSite } = require('./app.js');

const weeklyFindingsMock = [
  {
    source_type: 'СМИ',
    channel: 'СМИ',
    media_source: 'Sostav',
    placement: 'Sostav',
    date: '2026-06-25',
    title: 'Тестовое СМИ-упоминание',
    url: 'https://example.com/media-item'
  }
];

assert.equal(weeklyFindingsMock.filter(isMediaOrSite).length, 1);
assert.equal(isMediaOrSite(weeklyFindingsMock[0]), true);
