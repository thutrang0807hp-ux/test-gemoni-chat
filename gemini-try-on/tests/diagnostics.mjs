import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,existsSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {chromium} from '../runtime/node_modules/playwright-core/index.mjs';
import {run,failureMessage} from '../runtime/gemini.mjs';
const folder=mkdtempSync(join(tmpdir(),'gemini-diagnostics-'));
const profile=join(folder,'chrome');
const context=await chromium.launchPersistentContext(profile,{executablePath:process.env.CHROMIUM || '/usr/bin/chromium',headless:true,args:['--no-sandbox','--remote-debugging-port=0']});
try {
  await context.addCookies([{name:'__Secure-1PSID',value:'fixture-only',url:'https://gemini.google.com',secure:true}]);
  await context.pages()[0].route('https://gemini.google.com/**', route=>route.fulfill({contentType:'text/html; charset=utf-8',body:'<html><body><div role="textbox" contenteditable="true"></div><p>Không có nút gửi: fixture timeout</p></body></html>'}));
  const port=Number(readFileSync(join(profile,'DevToolsActivePort'),'utf8').split('\n')[0]);
  await assert.rejects(run(port,{action:'image',prompt:'fixture prompt',output:join(folder,'result'),diagnostics:folder}), error=>{
    assert.match(error.message,/Bước lỗi: điền prompt và bấm Gửi/);
    assert.match(error.message,/12000ms/);
    return true;
  });
  assert.equal(JSON.parse(readFileSync(join(folder,'status.json'),'utf8')).stage,'điền prompt và bấm Gửi');
  assert.ok(existsSync(join(folder,'last-error.png')));
  assert.ok(!existsSync(join(folder,'result')));
  assert.equal(failureMessage(new Error('detail\nsecret ignored'),'stage'),'Bước lỗi: stage. detail');
  console.log('PASS: real CDP timeout reports send stage, captures screenshot, no result or retries');
} finally {await context.close();rmSync(folder,{recursive:true,force:true});}
