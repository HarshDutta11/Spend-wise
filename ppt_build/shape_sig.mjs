import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("C:\\Users\\Harsh\\Desktop\\codeee\\SIH2026-IDEA-Presentation-Format.pptx"));
const x = p.resolve("sh/qx4nud0b");
console.log(Object.getOwnPropertyNames(Object.getPrototypeOf(x)));
console.log(typeof x.delete, x.delete?.toString());
