// Deployment smoke check: verify all public assets against this exact build.
// Runs on GitHub's deployment runner after Pages reports a successful publish.
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { importCSV, analyze, summarize } from '../src/engine.js';
const base = process.env.SITE_URL;
if (!base?.startsWith('https://')) throw new Error('Set SITE_URL to the HTTPS Pages deployment URL.');
const hash = buffer => createHash('sha256').update(buffer).digest('hex');
for (const path of ['index.html','styles.css','src/app.js','src/engine.js','samples/bank.csv','samples/receipts.csv','samples/invalid-bank.csv']) {
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
const bank = importCSV(await readFile('dist/samples/bank.csv','utf8'),'bank');
const receipts = importCSV(await readFile('dist/samples/receipts.csv','utf8'),'receipts');
const summary = summarize(analyze(bank, receipts));
if (summary.total !== 12 || summary.outstanding !== 6 || summary.exposure !== 59350) throw new Error('Unexpected deployed demo results.');
console.log('Public prototype verified: exact build assets, 12 demo transactions, 6 unresolved, $593.50.');
