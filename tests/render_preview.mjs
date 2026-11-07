/** Render simulated previews with real CDP viewport emulation; no household data. */
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const url = process.argv[2], output = process.argv[3];
if (!url || !output) throw new Error("Usage: render_preview.mjs URL OUTPUT_DIRECTORY");
const chrome = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
await mkdir(output, {recursive:true});
const profile=path.join(output,"browser-profile");
const port=19327;
const child=spawn(chrome,["--headless","--no-first-run","--no-default-browser-check","--disable-background-networking",
  "--allow-file-access-from-files",`--user-data-dir=${profile}`,`--remote-debugging-port=${port}`,"about:blank"],{stdio:"ignore"});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let socket;
try {
  let targets;
  for (let i=0;i<40;i++) {
    try {targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();break;} catch {await pause(100);}
  }
  const target=targets?.find(t=>t.type==="page");
  if (!target) throw new Error("Chrome did not start");
  socket=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.addEventListener("open",resolve,{once:true});socket.addEventListener("error",reject,{once:true});});
  let id=0;const pending=new Map();
  socket.addEventListener("message",event=>{
    const msg=JSON.parse(event.data);const entry=pending.get(msg.id);
    if(entry){pending.delete(msg.id);msg.error?entry.reject(new Error(msg.error.message)):entry.resolve(msg.result);}
  });
  const call=(method,params={})=>new Promise((resolve,reject)=>{
    const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));
  });
  const results=[];
  for (const [name,width,dark] of [["mobile",390,false],["desktop",1280,false],["mobile-dark",390,true]]) {
    await call("Emulation.setDeviceMetricsOverride",{width,height:1200,deviceScaleFactor:1,mobile:width<500});
    await call("Emulation.setEmulatedMedia",{features:[{name:"prefers-color-scheme",value:dark?"dark":"light"}]});
    await call("Page.navigate",{url});
    await pause(2000);
    const measurement=await call("Runtime.evaluate",{expression:`JSON.stringify({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,cardReady:!!document.querySelector('family-dual-lens-card')?._bitmap})`,returnByValue:true});
    const data=JSON.parse(measurement.result.value);results.push({name,...data});
    if (data.scrollWidth>data.width || !data.cardReady) throw new Error(`Preview failed: ${JSON.stringify(data)}`);
    const screenshot=await call("Page.captureScreenshot",{format:"png",captureBeyondViewport:true});
    await writeFile(path.join(output,`${name}.png`),Buffer.from(screenshot.data,"base64"));
  }
  await writeFile(path.join(output,"render-checks.json"),JSON.stringify(results,null,2));
  console.log(results);
} finally {
  socket?.close();child.kill("SIGTERM");
}
