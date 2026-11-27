import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {chromium} from '../runtime/node_modules/playwright-core/index.mjs';
import {run} from '../runtime/gemini.mjs';
const folder=mkdtempSync(join(tmpdir(),'gemini-roundtrip-'));
const profile=join(folder,'chrome');
const context=await chromium.launchPersistentContext(profile,{executablePath:process.env.CHROMIUM || '/usr/bin/chromium',headless:true,args:['--no-sandbox','--remote-debugging-port=0']});
const records=[];
let failUpload=false;
let pickerMode='existing';
const template = `<!DOCTYPE html><meta charset="utf-8"><style>img{width:64px;height:64px}</style>
<input type="file" accept="audio/*"><input id="images" type="file" multiple accept="image/*">
<div id="previews"></div><div role="textbox" contenteditable="true"></div><button id="send" aria-label="Send">Send</button><main></main>
<script>
const picker=document.querySelector('#images'), previews=document.querySelector('#previews'), send=document.querySelector('#send');
let files=[];
function wirePicker(picker) { picker.onchange=async()=>{
 send.disabled=true;
 files=await Promise.all([...picker.files].map(async file=>({name:file.name,base64:btoa(String.fromCharCode(...new Uint8Array(await file.arrayBuffer())))})));
 previews.innerHTML=files.map(file=>'<div class="different-composer-chip">'+file.name+'</div>').join('');
 // Stale hidden progress must not block upload completion.
 previews.insertAdjacentHTML('beforeend','<div class="upload-progress" hidden></div>');
 await fetch('/upload-fixture',{method:'POST',body:'upload'});
 send.disabled=false;
}; }
if (picker) wirePicker(picker);
const opener = document.querySelector('#open');
if (opener) opener.onclick = event => {
 if (!event.isTrusted) throw Error('untrusted opener');
 const openPicker = event => {
  if (!event.isTrusted) throw Error('untrusted menu');
  const input = document.createElement('input');
  input.type='file';input.multiple=true;input.accept='image/*';input.hidden=true;
  document.body.append(input);wirePicker(input);input.click();
 };
 if (opener.dataset.direct) return openPicker(event);
 const menu = document.createElement('div');menu.setAttribute('role','menu');
 const local = document.createElement('button');local.setAttribute('role','menuitem');local.innerText='Upload files';local.onclick=openPicker;
 menu.append(local);document.body.append(menu);
};
send.onclick=async event=>{
 if(!event.isTrusted)throw Error('untrusted submit');
 const prompt=document.querySelector('[role=textbox]').innerText;
 const answer=document.createElement('model-response');
 const rewrite=prompt.startsWith('Viết lại mô tả');
 const canvas=document.createElement('canvas');canvas.width=canvas.height=256;
 canvas.getContext('2d').fillStyle=prompt.includes('blue')?'blue':'green';canvas.getContext('2d').fillRect(0,0,256,256);
 const output=canvas.toDataURL('image/png');
 await fetch('/record',{method:'POST',body:JSON.stringify({prompt,files,output:rewrite?null:output})});
 if(rewrite)answer.innerHTML='<message-content>Prompt đã viết lại.</message-content>';
 else answer.innerHTML='<generated-image><img src="'+output+'"></generated-image>';
 document.querySelector('main').append(answer);
};
</script>`;
try {
 await context.addCookies([{name:'__Secure-1PSID',value:'fixture-only',url:'https://gemini.google.com',secure:true}]);
 await context.pages()[0].route('https://gemini.google.com/**',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/record'){records.push(route.request().postDataJSON());return route.fulfill({body:'ok'});}
  if(url.pathname==='/upload-fixture'){await new Promise(resolve=>setTimeout(resolve,300));return route.fulfill({status:failUpload?403:200,body:'ok'});}
  const controls = {
   menu:'<button id="open" aria-label="Open upload file menu">+</button>',
   icon:'<button id="open"><span class="google-symbols">add</span></button>',
   direct:'<button id="open" data-direct="yes" aria-label="Attach files">+</button>',
  };
  const body=controls[pickerMode]?template.replace('<input id="images" type="file" multiple accept="image/*">',controls[pickerMode]):template;
  return route.fulfill({contentType:'text/html; charset=utf-8',body});
 });
 const port=Number(readFileSync(join(profile,'DevToolsActivePort'),'utf8').split('\n')[0]);
 assert.deepEqual(await run(port,{action:'verify'}),{signedIn:true});
 assert.deepEqual(await run(port,{action:'prompt',prompt:'Viết prompt ảnh chân thực'}),{text:'Prompt đã viết lại.'});
 const original=join(folder,'original.png'),product=join(folder,'product.png');
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF1sAAAAASUVORK5CYII=','base64');
 writeFileSync(original,png);writeFileSync(product,Buffer.concat([png,Buffer.from('distinct bytes')]));
 const scenarios=[[],[original,product],[original,product],[original,product],[original,product],[]];
 const modes=['existing','existing','menu','icon','direct','existing'];
 for(let i=0;i<scenarios.length;i++){
  pickerMode=modes[i];
  const output=join(folder,'result-'+i+'.png');
  const prompt='Create '+(i%2?'blue':'green')+' image '+i;
  assert.deepEqual(await run(port,{action:'image',prompt,references:scenarios[i],output}),{saved:true});
  const record=records.at(-1);
  assert.ok(record.prompt.endsWith(prompt));
  assert.equal(record.files.length,scenarios[i].length);
  for(let j=0;j<record.files.length;j++) assert.deepEqual(Buffer.from(record.files[j].base64,'base64'),readFileSync(scenarios[i][j]));
  assert.deepEqual(readFileSync(output),Buffer.from(record.output.split(',')[1],'base64'));
 }
 failUpload=true;
 await assert.rejects(run(port,{action:'image',prompt:'must not submit',references:[original,product],output:join(folder,'failed.png')}), /từ chối tải ảnh tham chiếu/);
 assert.equal(records.length,7); // One rewrite, six generations; no retries.
 console.log('PASS: real CDP verify + rewrite + 6 full send/receive/save turns; with/without ordered references; alternate chips, hidden progress, delayed upload, audio picker ignored, lazy English menu, icon-only opener, native filechooser, trusted sends, exact output bytes');
} finally {await context.close();rmSync(folder,{recursive:true,force:true});}
