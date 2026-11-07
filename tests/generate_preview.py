"""Write a private visual-test page using simulated imagery, not camera footage."""
import pathlib
import sys

output = pathlib.Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
module = (pathlib.Path(__file__).parents[1] / "www/dual-lens-card.js").resolve().as_uri()
html = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {font:16px/1.5 Arial,sans-serif;margin:0;background:#f3f5f6;color:#172a32;
 --primary-text-color:#172a32;--secondary-text-color:#52616a;--card-background-color:#fff;--divider-color:#d5dfe3;}
main {max-width:560px;margin:24px auto;padding:0 16px;} h1 {font-size:24px;margin:0 0 16px;}
ha-card {display:block;background:var(--card-background-color);border-radius:16px;}
.test-label {font-size:12px;color:#52616a;}
@media(prefers-color-scheme:dark) {body {background:#101c22;color:#ecf2f5;
 --primary-text-color:#ecf2f5;--secondary-text-color:#b6c5cd;--card-background-color:#1b2c34;--divider-color:#40535d;}}
</style></head><body><main><h1>Camera controls</h1><p class="test-label">SIMULATED PREVIEW — no home camera data</p>
<family-dual-lens-card></family-dual-lens-card></main>
<script type="module">
import "MODULE";
const card=document.querySelector('family-dual-lens-card');
const states={'camera.example':{state:'idle'}};const buttons={};
for(const d of ['up','down','left','right','stop']) {buttons[d]='button.example_'+d;states[buttons[d]]={state:'unknown'};}
card.setConfig({entity:'camera.example',name:'Choose a camera view',buttons});
card.hass={states,callService:async()=>{},fetchWithAuth:async()=>{
 const canvas=document.createElement('canvas');canvas.width=640;canvas.height=720;const ctx=canvas.getContext('2d');
 for(const [y,color,text] of [[0,'#d8e8ed','UPPER VIEW'],[360,'#dde7d9','LOWER VIEW']]) {
  ctx.fillStyle=color;ctx.fillRect(0,y,640,360);ctx.fillStyle='#26414e';ctx.font='bold 28px Arial';ctx.fillText(text,32,y+48);
  ctx.strokeStyle='#93a9ad';ctx.lineWidth=2;ctx.strokeRect(32,y+80,576,244);
 }
 const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));return new Response(blob);
}};
</script></body></html>'''.replace("MODULE", module)
(output / "index.html").write_text(html)
print(output / "index.html")
