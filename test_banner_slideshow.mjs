import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');

test('editorial hero replaces retired rotating promotional banners', () => {
  assert.match(html, /<section class="hero-section" aria-labelledby="heroTitle">/);
  assert.match(html, /دقت در انتخاب/);
  assert.match(html, /<div class="hero-product-lineup">/);
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
