import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
const base=process.env.SITE_URL;
if(!base?.startsWith('https://'))throw Error('Set SITE_URL to the deployed HTTPS URL.');
const expected=await readFile('dist/index.html'),hash=b=>createHash('sha256').update(b).digest('hex');
let verified=false;
for(let attempt=0;attempt<6;attempt++){
 const response=await fetch(base,{signal:AbortSignal.timeout(15000),cache:'no-store'});
 if(response.ok&&hash(Buffer.from(await response.arrayBuffer()))===hash(expected)){verified=true;break;}
 if(attempt<5)await new Promise(r=>setTimeout(r,10000));
}
if(!verified)throw Error('Public HTML does not match the exact standalone build.');
console.log('Verified public HTTPS copy matches the complete offline HTML.');
