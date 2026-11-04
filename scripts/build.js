import { cp, mkdir, rm, readFile, writeFile } from "node:fs/promises";
import { build } from "esbuild";
await rm("dist", { recursive: true, force: true });
await mkdir("dist");
await mkdir("dist/legacy");
for (const item of ["index.html", "styles.css", "src", "samples"])
  await cp(item, `dist/legacy/${item}`, { recursive: true });
await cp("agent_samples", "dist/agent_samples", {recursive: true});
await cp("agent_workspace/web/workspace.css", "dist/workspace.css");
await cp("node_modules/pdfjs-dist/build/pdf.worker.min.mjs", "dist/pdf.worker.min.mjs");
let html = await readFile("agent_workspace/web/index.html", "utf8");
html = html.replace("Choose tools &amp; collect evidence", "Fixed evidence checklist").replace("Choose tools & collect evidence", "Fixed evidence checklist").replace("Server-stored demonstration runs", "Runs saved only in this browser");
html = html.replace('<meta charset="utf-8" />', '<meta charset="utf-8" /><meta name="ledgerlens-runtime" content="guided" />');
html = html.replace('<main>', '<main><div class="notice" id="public-disclosure"><strong>Public workflow demo · no live LLM.</strong> Read PDFs, investigate evidence, record decisions, and resume a case here. The model-driven LangGraph + Ollama version is included in the <a href="https://github.com/ayaan-27/Miraflores_Project#readme" target="_blank" rel="noopener">source and setup guide</a>.</div>');
await writeFile("dist/index.html", html);
await build({entryPoints: ["agent_workspace/web/workspace.js"], outdir: "dist", bundle: true, splitting: true, format: "esm", target: "es2022", entryNames: "[name]", chunkNames: "[name]-[hash]", legalComments: "eof", minify: true, sourcemap: false});
console.log(
  "Built the public PDF workflow demo in dist/ and the previous prototype in dist/legacy/. No inference API or paid host is used.",
);
