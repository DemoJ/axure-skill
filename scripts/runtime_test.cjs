// Optional verification of Axure's REAL exported runtime. Uses a headless
// browser and an ephemeral loopback server; no desktop input or visible window.
const {strict:assert}=require('assert');
const http=require('http'),fs=require('fs'),path=require('path');
let chromium;
try { ({chromium}=require('playwright')); }
catch(error){
  if(process.argv[2]!=='--doctor')throw error;
  process.stdout.write(JSON.stringify({ok:false,playwright:false,browser_available:false})+'\n');
  process.exit(1);
}
if(process.argv[2]==='--doctor'){
  const executable=process.env.AXURE_TEST_BROWSER||chromium.executablePath();
  const available=fs.existsSync(executable);
  process.stdout.write(JSON.stringify({ok:available,playwright:true,browser_available:available,executable})+'\n');
  process.exit(available?0:1);
}

(async()=>{
  const root=path.resolve(process.argv[2]);
  const planPath=path.resolve(process.argv[3]);
  const plan=JSON.parse(fs.readFileSync(planPath,'utf8').replace(/^\uFEFF/,''));
  const screenshot=process.argv[4]&&path.resolve(process.argv[4]);
  const server=http.createServer((req,res)=>{
    try {
      const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
      if(!file.startsWith(root+path.sep))throw Error('Outside export');
      res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html','.png':'image/png','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream');
      res.end(fs.readFileSync(file));
    }catch{res.writeHead(404);res.end();}
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  let browser;
  const errors=[],checks=[],screenshots=[];
  try {
    const options={headless:true};
    if(process.env.AXURE_TEST_BROWSER)options.executablePath=process.env.AXURE_TEST_BROWSER;
    browser=await chromium.launch(options);
    const page=await browser.newPage({viewport:plan.viewport||{width:1240,height:900}});
    page.setDefaultTimeout(8000);
    page.on('pageerror',error=>errors.push(error.message));
    const base='http://127.0.0.1:'+server.address().port+'/';
    for(const step of plan.steps){
      process.stderr.write('Checking: '+(step.name||step.target||step.open)+'\n');
      if(step.viewport)await page.setViewportSize(step.viewport);
      const locator=step.target?page.locator('[data-label='+JSON.stringify(step.target)+']'):null;
      if(step.open)await page.goto(base+encodeURIComponent(step.open)+'.html');
      if(step.click)await page.locator('[data-label='+JSON.stringify(step.click)+']').click();
      if(step.hover)await page.locator('[data-label='+JSON.stringify(step.hover)+']').hover();
      if(step.fill!==undefined){const input=locator.locator('input,textarea');await input.click();await input.fill(step.fill);assert.equal(await input.inputValue(),step.fill);}
      if(step.wait)await page.waitForTimeout(step.wait);
      if(step.visible!==undefined)await locator.waitFor({state:step.visible?'visible':'hidden'});
      if(step.text!==undefined){
        try { await page.waitForFunction(({name,text})=>[...document.querySelectorAll('[data-label]')].filter(e=>e.getAttribute('data-label')===name).some(e=>e.innerText.trim()===text),{name:step.target,text:step.text}); }
        catch(error){throw Error('Expected '+step.target+' text '+JSON.stringify(step.text)+'; actual '+JSON.stringify(await locator.evaluate(el=>({text:el.innerText,html:el.outerHTML})))+'; browser errors '+JSON.stringify(errors));}
      }
      if(step.texts)assert.deepEqual(await locator.allTextContents().then(xs=>xs.map(x=>x.trim())),step.texts);
      if(step.value!==undefined)assert.equal(await locator.locator('input,textarea,select').inputValue(),step.value);
      if(step.checked!==undefined)assert.equal(await locator.locator('input').isChecked(),step.checked);
      if(step.disabled!==undefined)assert.equal(await locator.locator('input,textarea,select').isDisabled(),step.disabled);
      if(step.focused!==undefined)assert.equal(await locator.evaluate(el=>el.contains(document.activeElement)),step.focused,'Focus of '+step.target);
      if(step.options)assert.deepEqual(await locator.locator('option').allTextContents(),step.options);
      if(step.url)await page.waitForURL(url=>decodeURIComponent(url.pathname)==='/'+step.url+'.html');
      if(step.style)for(const [property,expected] of Object.entries(step.style))assert.equal(await locator.evaluate((el,p)=>getComputedStyle(el)[p],property),expected,step.target+'.'+property);
      if(step.visual_style)for(const [property,expected] of Object.entries(step.visual_style))assert.equal(await locator.locator('[id$="_div"]').evaluate((el,p)=>getComputedStyle(el)[p],property),expected,step.target+' visual '+property);
      if(step.rotation!==undefined){
        const rotation=await locator.evaluate(el=>{const m=new DOMMatrixReadOnly(getComputedStyle(el).transform);return Math.atan2(m.b,m.a)*180/Math.PI;});
        assert.ok(Math.abs(rotation-step.rotation)<0.01,'Rotation of '+step.target+': '+rotation);
      }
      if(step.page_alignment){
        assert.ok(['left','center'].includes(step.page_alignment),'Unknown page alignment');
        const geometry=await page.evaluate(()=>{
          const body=document.body.getBoundingClientRect();
          const style=getComputedStyle(document.body);
          // RP9 trims a positive canvas origin using a negative relative left.
          // Measure the exported content origin, not that compensating body box.
          const offset=style.position==='relative'?(parseFloat(style.left)||0):0;
          return {x:body.x-offset,width:body.width,viewport:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth};
        });
        const expected=step.page_alignment==='center'?Math.max(0,(geometry.viewport-geometry.width)/2):0;
        assert.ok(Math.abs(geometry.x-expected)<=1,'Page alignment '+step.page_alignment+': '+JSON.stringify(geometry));
        if(geometry.width<=geometry.viewport)assert.ok(geometry.scrollWidth<=geometry.viewport+1,'Unexpected horizontal overflow');
        if(step.canvas){
          const canvas=await page.locator('[data-label='+JSON.stringify(step.canvas)+']').boundingBox();
          assert.ok(canvas,'Canvas must be visible');
          const canvasX=step.page_alignment==='center'?Math.max(0,(geometry.viewport-canvas.width)/2):0;
          assert.ok(Math.abs(canvas.x-canvasX)<=1,'Visible canvas alignment: '+JSON.stringify(canvas));
        }
      }
      const shot=typeof step.screenshot==='string'?path.resolve(path.dirname(planPath),step.screenshot):step.screenshot&&screenshot;
      if(shot){fs.mkdirSync(path.dirname(shot),{recursive:true});await page.screenshot({path:shot,fullPage:true});screenshots.push(shot);}
      checks.push(step.name||JSON.stringify(step));
    }
    assert.deepEqual(errors,[],'JavaScript runtime errors');
    process.stdout.write(JSON.stringify({ok:true,engine:'Axure exported runtime / headless Chromium',checks,browser_errors:errors,screenshot,screenshots},null,2)+'\n');
  }finally {if(browser)await browser.close();await new Promise(r=>server.close(r));}
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
