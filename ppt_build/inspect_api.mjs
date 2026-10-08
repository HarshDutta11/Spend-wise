import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("C:\\Users\\Harsh\\Desktop\\codeee\\SIH2026-IDEA-Presentation-Format.pptx"));
console.log(Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides)));
console.log(Object.keys(p.slides));
