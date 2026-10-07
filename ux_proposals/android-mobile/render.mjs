import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const root=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(root,'mockups');
mkdirSync(out,{recursive:true});
const chrome='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const screens=['workbench','evidence','review'];
const sizes=process.argv.includes('--all')?[[360,800],[390,844],[412,915]]:[[390,844]];
const results=[];
const proc=spawn(chrome,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-extensions','--disable-background-networking','--disable-component-update','--disable-sync','--hide-scrollbars','--remote-debugging-pipe',`--user-data-dir=${path.join(root,'render-profile-device')}`],{windowsHide:true,stdio:['ignore','ignore','pipe','pipe','pipe']});
let seq=0,buffer='';const pending=new Map();let errors='';proc.stderr.on('data',d=>{errors=(errors+d.toString()).slice(-2000)});
proc.stdio[4].on('data',d=>{buffer+=d.toString();let end;while((end=buffer.indexOf('\0'))!==-1){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);if(!line)continue;const message=JSON.parse(line);if(message.id){const p=pending.get(message.id);if(p){clearTimeout(p.timer);pending.delete(message.id);message.error?p.reject(new Error(JSON.stringify(message.error))):p.resolve(message.result)}}}});
function call(method,params={},sessionId){return new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`Timeout: ${method} ${errors}`))},15000);pending.set(id,{resolve,reject,timer});proc.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0')})}
try{
 for(const [width,height] of sizes){
  for(const screen of screens){
   const target=await call('Target.createTarget',{url:'about:blank'});
   const {sessionId}=await call('Target.attachToTarget',{targetId:target.targetId,flatten:true});
   await call('Page.enable',{},sessionId);
   await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:2,mobile:true},sessionId);
   const url=pathToFileURL(path.join(root,'index.html')).href+'?screen='+screen;
   await call('Page.navigate',{url},sessionId);
   let audit;
   for(let attempt=0;attempt<20;attempt++){
    const result=await call('Runtime.evaluate',{expression:"new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(document.querySelector('#qa')?.textContent||''))))",awaitPromise:true,returnByValue:true},sessionId);
    if(result.result.value){audit=JSON.parse(result.result.value);if(audit.screen===screen&&audit.width===width&&audit.height===height)break}
    await new Promise(r=>setTimeout(r,50));
   }
   if(!audit||audit.width!==width||audit.height!==height)throw new Error('Device metrics mismatch '+JSON.stringify(audit));
   await call('Runtime.evaluate',{expression:"window.scrollTo(0,0);document.querySelector('.main').scrollTop=0;",returnByValue:true},sessionId);
   await new Promise(r=>setTimeout(r,350));
   const {data}=await call('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:true,clip:{x:0,y:0,width,height,scale:1}},sessionId);
   const file=path.join(out,`alephtav-${screen}-${width}x${height}.png`);
   const png=Buffer.from(data,'base64');writeFileSync(file,png);
   const result={screen,requested:[width,height],audit,pixels:[png.readUInt32BE(16),png.readUInt32BE(20)],file,saved:true};
   results.push(result);console.log(JSON.stringify(result));
   await call('Target.closeTarget',{targetId:target.targetId});
  }
 }
 writeFileSync(path.join(out,'validation.json'),JSON.stringify(results,null,2));
 const board=await call('Target.createTarget',{url:'about:blank'});
 const boardSession=(await call('Target.attachToTarget',{targetId:board.targetId,flatten:true})).sessionId;
 await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1140,deviceScaleFactor:1,mobile:false},boardSession);
 await call('Page.navigate',{url:pathToFileURL(path.join(root,'board.html')).href},boardSession);
 await new Promise(r=>setTimeout(r,600));
 const boardCapture=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:1440,height:1140,scale:1}},boardSession);
 writeFileSync(path.join(out,'alephtav-android-first-review.png'),Buffer.from(boardCapture.data,'base64'));
 await call('Browser.close');
}catch(error){console.error(error);proc.kill();process.exitCode=1}
