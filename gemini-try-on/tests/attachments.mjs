import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync, mkdtempSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {chromium} from '../runtime/node_modules/playwright-core/index.mjs';
import {attachReferences} from '../runtime/gemini.mjs';

// Prove that the original sender and all image-result helpers are unchanged.
const original = execFileSync('git', ['show', '75f43c93a5670acc65ce1411ffb2ea298db348f0:gemini-try-on/runtime/gemini.mjs'], {encoding:'utf8'});
const updated = readFileSync(new URL('../runtime/gemini.mjs', import.meta.url), 'utf8');
for (const name of ['imageSource','imageInstruction','editorFor','submit','waitForText','waitForImage','downloadImage','downloadFromGemini','copyImagePixels','saveResult']) {
  const extract = text => text.match(new RegExp('(?:export )?(?:async )?function '+name+'\\([^]*?\\n}'))?.[0];
  assert.ok(extract(original), name);
  assert.equal(extract(updated), extract(original), `${name} changed`);
}
const browser = await chromium.launch({executablePath:process.env.CHROMIUM || '/usr/bin/chromium', headless:true, args:['--no-sandbox']});
const folder = mkdtempSync(join(tmpdir(), 'gemini-refs-'));
const paths = [join(folder, 'original.png'), join(folder, 'product.png')];
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF1sAAAAASUVORK5CYII=', 'base64');
paths.forEach(path => writeFileSync(path, png));
try {
  const page = await browser.newPage();
  await attachReferences(page, undefined); // original no-attachment path touches nothing
  for (let turn=0; turn<3; turn++) {
    await page.setContent(`<style>uploader-file-preview {display:block; width:20px; height:20px}</style><input type="file" multiple><div id="previews"></div><script>
      document.querySelector('input').onchange = async event => {
        window.files = await Promise.all([...event.target.files].map(async f => ({name:f.name, bytes:[...new Uint8Array(await f.arrayBuffer())]})));
        document.querySelector('#previews').innerHTML = window.files.map(() => '<uploader-file-preview></uploader-file-preview>').join('');
      };
    </script>`);
    // Browser file API preserves binary payload and order across multiple turns.
    await attachReferences(page, paths);
    const files = await page.evaluate(() => window.files);
    assert.equal(files.length, 2);
    for (let i=0; i<2; i++) assert.deepEqual(files[i].bytes, [...readFileSync(paths[i])]);
  }
  await page.setContent(`<input type="file" multiple><div id="previews"></div><script>
    document.querySelector('input').onchange = event => {
      document.querySelector('#previews').innerText = [...event.target.files].map(file => file.name).join(' ');
    };
  </script>`);
  const previous = execFileSync('git', ['show', '3273e62:gemini-try-on/runtime/gemini.mjs'], {encoding:'utf8'});
  const oldSource = previous.slice(previous.indexOf('export async function attachReferences'), previous.indexOf('export function failureMessage')).replace('export ', '');
  const oldAttach = Function('return (' + oldSource + ')')();
  const wait = page.waitForFunction.bind(page);
  page.waitForFunction = (fn, arg, options) => wait(fn, arg, {...options, timeout:800});
  await assert.rejects(oldAttach(page, paths), /Timeout/);
  page.waitForFunction = wait;
  await attachReferences(page, paths);
  console.log('PASS: previous uploader times out on filename chips; replacement succeeds on the same page');
  await assert.rejects(attachReferences(page, [null]), /không hợp lệ/);
  await assert.rejects(attachReferences(page, ['/nonexistent/image.png']));
  console.log('PASS: original 10 helpers unchanged; no-reference path; 3 ordered binary uploads; invalid/missing files rejected');
} finally { await browser.close(); rmSync(folder, {recursive:true, force:true}); }
