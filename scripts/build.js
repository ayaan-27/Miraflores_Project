import {mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {build} from 'esbuild';
const bundle=await build({entryPoints:['submission/app.js'],bundle:true,format:'iife',target:'es2022',write:false,minify:true,legalComments:'eof'});
const js=bundle.outputFiles[0].text.replaceAll('</script','<\\/script');
const html=(await readFile('submission/template.html','utf8')).replace('/* APP_SCRIPT */',()=>js);
await rm('dist',{recursive:true,force:true});await mkdir('dist');
await writeFile('dist/index.html',html);await writeFile('submission/OPEN_THIS.html',html);
console.log('Built self-contained offline app and identical Pages copy.');
