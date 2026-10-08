import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const input = "C:\\Users\\Harsh\\Desktop\\final project\\ppt_output\\DELTA_h_SPENDWISE_SIH2026_v5.pptx";
const out = "C:\\Users\\Harsh\\Desktop\\final project\\ppt_reference\\final";
await fs.mkdir(out, { recursive: true });
const p = await PresentationFile.importPptx(await FileBlob.load(input));
for (let i = 0; i < p.slides.items.length; i++) {
  const blob = await p.slides.getItem(i).export({ format: "png", scale: 1 });
  await fs.writeFile(path.join(out, `slide-${i + 1}.png`), new Uint8Array(await blob.arrayBuffer()));
}
const montage = await p.export({ format: "png", montage: true, scale: 1 });
await fs.writeFile(path.join(out, "montage.png"), new Uint8Array(await montage.arrayBuffer()));
