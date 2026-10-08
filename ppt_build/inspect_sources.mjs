import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const source = "C:\\Users\\Harsh\\Desktop\\codeee\\SIH2026-IDEA-Presentation-Format.pptx";
const out = "C:\\Users\\Harsh\\Desktop\\final project\\ppt_reference";
await fs.mkdir(out, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
const snapshot = await presentation.inspect({
  kind: "deck,slide,textbox,shape,image,table,chart,notes,layout",
  maxChars: 30000,
});
await fs.writeFile(path.join(out, "template-inspect.ndjson"), snapshot.ndjson);
const montage = await presentation.export({ format: "png", montage: true, scale: 1 });
await fs.writeFile(path.join(out, "template-montage.png"), new Uint8Array(await montage.arrayBuffer()));
for (let i = 0; i < presentation.slides.items.length; i++) {
  const slide = presentation.slides.getItem(i);
  const image = await slide.export({ format: "png", scale: 1 });
  await fs.writeFile(path.join(out, `template-slide-${i + 1}.png`), new Uint8Array(await image.arrayBuffer()));
}
console.log(JSON.stringify({slides: presentation.slides.items.length, masters: presentation.masters.items.length, layouts: presentation.layouts.items.length, size: presentation.slideSize}));
