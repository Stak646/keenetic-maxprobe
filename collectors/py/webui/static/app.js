async function jget(u){const r=await fetch(u,{cache:'no-store'});return await r.json();}
async function jpost(u,o){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});return await r.json();}
function fmtBytes(n){if(n===undefined||n===null)return '-';const u=['B','KB','MB','GB','TB'];let i=0,x=Number(n);while(x>=1024&&i<u.length-1){x/=1024;i++;}return x.toFixed(i?2:0)+' '+u[i];}
async function refresh(){const st=await jget('/api/status');const dot=document.getElementById('dot');const line=document.getElementById('line');
dot.className=st.running?'dot run':'dot idle';line.textContent=st.running?('running pid='+st.pid):'idle';
document.getElementById('phase').textContent=st.phase||'-';document.getElementById('progress').textContent=st.progress||'-';
if(st.metrics){document.getElementById('cpu').textContent=st.metrics.cpu+'%';document.getElementById('mem').textContent=st.metrics.mem+'%';document.getElementById('load1').textContent=st.metrics.load1;}
const box=document.getElementById('archives');box.innerHTML='';(st.archives||[]).forEach(a=>{const div=document.createElement('div');const sha=a.sha256?` • <a href="/download/${a.sha256}">${a.sha256}</a>`:'';div.innerHTML=`<a href="/download/${a.name}">${a.name}</a> • ${fmtBytes(a.size)}${sha}`;box.appendChild(div);});
}
async function refreshLog(){const r=await jget('/api/log');document.getElementById('log').textContent=(r.log||'').trimEnd();}
async function start(){const profile=document.getElementById('profile').value;const mode=document.getElementById('mode').value;const collectors=document.getElementById('collectors').value;const deps_level=document.getElementById('deps_level').value;
const resp=await jpost('/api/start',{profile,mode,collectors,deps_level});document.getElementById('resp').textContent=JSON.stringify(resp);}
document.getElementById('start').addEventListener('click',start);
setInterval(()=>{refresh().catch(()=>{});refreshLog().catch(()=>{});},1200);refresh();refreshLog();
