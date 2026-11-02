import { cp, mkdir, rm } from "node:fs/promises";
await rm("dist", { recursive: true, force: true });
await mkdir("dist");
for (const item of ["index.html", "styles.css", "src", "samples"])
  await cp(item, `dist/${item}`, { recursive: true });
console.log(
  "Static production site built in dist/. No runtime dependencies or API keys.",
);
