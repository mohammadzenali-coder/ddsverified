import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');

test('editorial hero replaces retired rotating promotional banners', () => {
  assert.match(html, /<section class="hero-section" aria-labelledby="heroTitle">/);
  assert.match(html, /کیفیت تایید شده<br><em>مدل های متنوع<\/em>/);
  assert.match(html, /<div class="hero-product-lineup" id="heroProductLineup">/);
  assert.match(html, /href="#categoryLinks"/);
  assert.match(html, /id="categoryLinks"/);
  assert.match(html, /\.why-cards \{ grid-template-columns: repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(html, /مسئول علمی مجموعه : دکتر محمد رضا زینلی DMD DDS/);
  for (const image of ['lux.webp', 'endozburbanner.webp', 'banner-2-high.webp']) {
    assert.ok(!html.includes(image), `retired banner ${image} is absent`);
  }
});

test('featured product images are local and hero works without JavaScript', () => {
  const hero = html.split('<section class="hero-section"', 2)[1].split('</section>', 1)[0];
  const images = [...hero.matchAll(/<img src="(images\/[^"]+)"/g)].map(m => m[1]);
  assert.equal(images.length, 3);
  for (const image of images) assert.ok(existsSync(new URL(image, import.meta.url)), `${image} exists`);
  assert.match(hero, /fetchpriority="high"/);
  assert.match(hero, /href="#productGrid"/);
});

test('hero rotations use three distinct model shapes on a five-second interval', () => {
  assert.match(html, /function initHeroRotation\(\)/);
  assert.match(html, /const picks = \[\], shapes = new Set\(\)/);
  assert.match(html, /previous\.has\(p\.model\) \|\| shapes\.has\(p\.shape\)/);
  assert.match(html, /window\.setInterval\(rotate, 5000\)/);
});
