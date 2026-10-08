import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("C:\\Users\\Harsh\\Desktop\\codeee\\SIH2026-IDEA-Presentation-Format.pptx"));
console.log(p.slides.remove.toString());
