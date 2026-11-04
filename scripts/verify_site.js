// Verify the public workflow demo against the exact build deployed by Pages.
import { createHash } from 'node:crypto';
import { readFile, readdir, stat } from 'node:fs/promises';
const base = process.env.SITE_URL;
if (!base?.startsWith('https://')) throw new Error('Set SITE_URL to the HTTPS Pages deployment URL.');
const hash = buffer => createHash('sha256').update(buffer).digest('hex');
const files = (await readdir('dist', {recursive:true})).filter(path => !path.startsWith('legacy/') || ['legacy/index.html','legacy/src/engine.js'].includes(path));
for (const path of files) {
  if (!(await stat(`dist/${path}`)).isFile()) continue;
  const expected = await readFile(`dist/${path}`);
  let verified = false;
  for (let attempt = 0; attempt < 6; attempt++) {
    const response = await fetch(new URL(path, base.endsWith('/') ? base : base + '/'), {signal:AbortSignal.timeout(15000),cache:'no-store'});
    if (response.ok && hash(Buffer.from(await response.arrayBuffer())) === hash(expected)) { verified = true; break; }
    if (attempt < 5) await new Promise(resolve=>setTimeout(resolve, 10000));
  }
  if (!verified) throw new Error(`Deployed asset did not match the current build: ${path}`);
  console.log(`Verified deployed asset: ${path}`);
}
const html = await readFile('dist/index.html','utf8');
if (!html.includes('content="guided"') || !html.includes('no live LLM')) throw new Error('Public execution-mode disclosure missing.');
console.log('Public workflow demo verified: exact assets and sample PDFs, explicit no-LLM disclosure, and legacy archive.');
