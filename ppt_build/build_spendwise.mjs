import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const skillDir = "C:\\Users\\Harsh\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.904.11930\\skills\\presentations";
const runtimePython = "C:\\Users\\Harsh\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const workspaceDir = "C:\\Users\\Harsh\\Desktop\\final project";
const templatePath = "C:\\Users\\Harsh\\Desktop\\codeee\\SIH2026-IDEA-Presentation-Format.pptx";
const templateSha256 = createHash("sha256").update(await fs.readFile(templatePath)).digest("hex");
const finalPath = path.join(workspaceDir, "ppt_output", "DELTA_h_SPENDWISE_SIH2026_v5.pptx");
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
const utils = await import(pathToFileURL(path.join(skillDir, "container_tools", "artifact_tool_utils.mjs")).href);
await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(finalPath), { recursive: true });

const p = await PresentationFile.importPptx(await FileBlob.load(templatePath));

function replace(id, oldText, newText) {
  const target = p.resolve(id);
  target.text = newText;
}

function addHeading(slide, text, top) {
  const heading = slide.shapes.add({ geometry: "textbox", position: { left: 42, top, width: 1120, height: 44 }, fill: "none", line: { fill: "none", width: 0 } });
  heading.text = text;
  heading.text.style = { typeface: "Arial", fontSize: 26, bold: true, color: "#123B60", autoFit: "shrinkText" };
}

function addBullets(slide, items, top, height, fontSize = 22) {
  const body = slide.shapes.add({ geometry: "textbox", position: { left: 42, top, width: 1140, height }, fill: "none", line: { fill: "none", width: 0 } });
  body.text = utils.makeNativeBulletParagraphs(items, { marginLeftPoints: 20, hangingPoints: 10, spaceAfterPoints: 7 });
  body.text.style = { typeface: "Arial", fontSize, color: "#000000", autoFit: "shrinkText" };
}

function addFlowRow(slide, items, top, options = {}) {
  const left = options.left ?? 48;
  const width = options.width ?? 218;
  const gap = options.gap ?? 18;
  const height = options.height ?? 94;
  const fills = options.fills ?? ["#EAF3FB", "#F6F9FC"];
  for (let i = 0; i < items.length; i++) {
    const box = slide.shapes.add({
      geometry: "roundRect",
      position: { left: left + i * (width + gap), top, width, height },
      fill: fills[i % fills.length],
      line: { fill: "#0070C0", width: 1.5 },
    });
    box.text = items[i];
    box.text.style = { typeface: "Arial", fontSize: options.fontSize ?? 16, color: "#123B60", autoFit: "shrinkText" };
  }
}

// Slide 1: preserve official fields, complete only known team details.
replace("sh/7qp4be9c", "TITLE PAGE", "SPENDWISE");
replace("sh/wn6dc7eh", "Problem Statement ID –\nProblem Statement Title-\nTheme-\nPS Category- Software/Hardware\nTeam ID-\nTeam Name (Registered on portal)", "Problem Statement ID -\nProblem Statement Title -\nTheme -\nPS Category -\nTeam ID - 033\nTeam Name - DELTA h");

// Slide 2: problem and proposed product, stated as editable bullet text.
replace("sh/dkvmpszm", "IDEA TITLE", "SPENDWISE");
replace("sh/qx4nud0b", "Proposed Solution (Describe your Idea/Solution/Prototype)\n\n\nDetailed explanation of the proposed solution\n How it addresses the problem\nInnovation and uniqueness of the solution ", "Student Financial Intelligence & AI Coach\n\n• Record expenses quickly with categories, budgets and DD-MM-YYYY dates\n• Explain cash flow through runway, daily burn rate and safe daily spend\n• Forecast budget pressure and suggest practical savings actions\n• Support action with an AI coach, micro-roundups, goals, bill splitting and student offers");
replace("sh/ove9o7yd", "Your Team Name", "DELTA h");
const s2 = p.slides.getItem(1);
p.resolve("sh/qx4nud0b").delete();
addHeading(s2, "Student Financial Intelligence & AI Coach", 166);
addBullets(s2, [
  "Record expenses quickly with categories, budgets and DD-MM-YYYY dates",
  "Explain cash flow through runway, daily burn rate and safe daily spend",
  "Forecast budget pressure and suggest practical savings actions",
  "Support action with an AI coach, micro-roundups, goals, bill splitting and student offers",
], 226, 330, 22);
addHeading(s2, "Student journey", 470);
addFlowRow(s2, ["1. LOG\nExpense or income", "2. UNDERSTAND\nBudget and trends", "3. DECIDE\nSafe daily spend", "4. ACT\nCoach and savings"], 525, { width: 272, gap: 16, height: 80, fontSize: 15 });

// Slide 3: architecture with native, editable stages.
replace("sh/1k3214v2", "Technologies to be used (e.g. programming languages, frameworks, hardware)\nMethodology and process for implementation (Flow Charts/Images/ working prototype)", "Technology stack: Flask, Python, SQLite/MySQL, Jinja templates, HTML/CSS and JavaScript\n\nThe five-stage Student Financial Intelligence engine converts day-to-day activity into clear next actions.");
replace("sh/m1c3mlsn", "Your Team Name", "DELTA h");
const s3 = p.slides.getItem(2);
p.resolve("sh/1k3214v2").delete();
addHeading(s3, "Technology stack and implementation", 158);
addBullets(s3, [
  "Flask, Python, SQLite/MySQL, Jinja templates, HTML/CSS and JavaScript",
  "A five-stage Student Financial Intelligence engine converts activity into clear next actions",
], 212, 132, 20);
addHeading(s3, "Student Financial Intelligence workflow", 378);
const stages = [
  ["1. RECORD", "Transactions\nBudgets\nGoals"],
  ["2. UNDERSTAND", "Category trends\nHealth score"],
  ["3. PREDICT", "Runway\nSafe daily spend"],
  ["4. RECOMMEND", "AI coach\nBudget alerts"],
  ["5. ACHIEVE", "Roundups\nSavings goals"],
];
for (let i = 0; i < stages.length; i++) {
  const box = s3.shapes.add({
    geometry: "roundRect",
    position: { left: 48 + i * 236, top: 475, width: 200, height: 128 },
    fill: i % 2 ? "#E9F2FB" : "#F7FAFD",
    line: { fill: "#0070C0", width: 1.5 },
  });
  box.text = `${stages[i][0]}\n${stages[i][1]}`;
  box.text.style = { typeface: "Arial", fontSize: 16, color: "#123B60", bold: false, autoFit: "shrinkText" };
}

// Slide 4: feasibility and safeguards.
replace("sh/sjad83id", "Analysis of the feasibility of the idea\nPotential challenges and risks\nStrategies for overcoming these challenges", "• Feasible MVP: Flask app, local SQLite data store and responsive web interface already implemented\n• Modular services separate transaction records, financial calculations, reports and AI assistance\n• Privacy: keep financial data scoped to the user and make AI support optional\n• Reliability: input validation, budget-limit warnings and automated tests support predictable behaviour");
replace("sh/i94r6xgz", "Your Team Name", "DELTA h");
const s4 = p.slides.getItem(3);
p.resolve("sh/sjad83id").delete();
addHeading(s4, "Implementation readiness", 160);
addBullets(s4, [
  "Feasible MVP: Flask app, local SQLite data store and responsive web interface already implemented",
  "Modular services separate records, calculations, reports and AI assistance",
], 215, 100, 18);
addHeading(s4, "Application architecture", 330);
addFlowRow(s4, ["INPUTS\nTransactions\nBudgets\nGoals", "FINANCE ENGINE\nRunway\nHealth score\nBudget checks", "USER EXPERIENCE\nDashboard\nCoach\nReports", "ACTION\nSavings goals\nRoundups\nBill split"], 390, { width: 272, gap: 16, height: 130, fontSize: 15, fills: ["#EAF3FB", "#FDF4DD", "#EAF8F1", "#FBEAEC"] });
addBullets(s4, ["Safeguards: user-scoped data, input validation, budget-limit warnings and automated tests"], 545, 55, 16);

// Slide 5: impact grounded in the product's known functions.
replace("sh/g7alsnu1", "Potential impact on the target audience\nBenefits of the solution (social, economic, environmental, etc.)", "• Helps Indian college students see how long their current money can last\n• Makes daily spending decisions easier with a safe-spend amount and budget warnings\n• Turns spare change into progress through UPI-style micro-roundups and savings goals\n• Reduces friction in shared campus expenses with an in-app bill splitter\n• Surfaces student offers so users can identify relevant discounts");
replace("sh/ahkvi1cb", "Your Team Name", "DELTA h");
const s5 = p.slides.getItem(4);
p.resolve("sh/g7alsnu1").delete();
addHeading(s5, "Demo data snapshot from the app database", 160);
addFlowRow(s5, ["FOOD SPEND\n₹12,945", "BILLS SPEND\n₹9,500", "TRANSPORT SPEND\n₹1,648", "MACBOOK GOAL\n₹62,000 / ₹95,000"], 220, { width: 272, gap: 16, height: 92, fontSize: 16, fills: ["#FDF4DD", "#FBEAEC", "#EAF3FB", "#EAF8F1"] });
addHeading(s5, "Savings progress", 350);
addFlowRow(s5, ["Emergency cushion\n₹32,000 / ₹45,000\n71% funded", "Hackathon trip\n₹7,800 / ₹12,000\n65% funded", "Decision support\nBudget checks\nSafe-spend guidance", "Campus support\nBill split\nStudent offers"], 410, { width: 272, gap: 16, height: 125, fontSize: 15 });
addBullets(s5, ["The values above come from the seeded local demo database and remain editable in this presentation"], 560, 35, 15);

// Slide 6: traceable project references only; no unsupported external claims.
replace("sh/vq5cve1s", "Details / Links of the reference and research work", "Project references\n\n• app.py - Flask routes and application workflow\n• finance_engine.py - runway, daily-spend and financial-health calculations\n• db.py - SQLite/MySQL data access\n• templates/dashboard.html - student finance cockpit interface\n• test_finance.py - automated calculation tests");
replace("sh/pc76hkr2", "Your Team Name", "DELTA h");
const s6 = p.slides.getItem(5);
p.resolve("sh/vq5cve1s").delete();
addHeading(s6, "Project references", 175);
addBullets(s6, [
  "app.py - Flask routes and application workflow",
  "finance_engine.py - runway, daily-spend and financial-health calculations",
  "db.py - SQLite/MySQL data access",
  "templates/dashboard.html - student finance cockpit interface",
  "test_finance.py - automated calculation tests",
], 235, 335, 20);

// The seventh source slide contains submission instructions and is not part of the six-slide deliverable.
p.slides.remove(6);

const { finalizePresentation } = utils;
const candidatePath = path.join(stagingDir, "spendwise-candidate.pptx");
await (await PresentationFile.exportPptx(p)).save(candidatePath);
const result = await finalizePresentation({
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  explicitTotalSlideCount: 6,
  fontPolicy: { basis: "reference", families: ["Arial", "Calibri", "Garamond", "Times New Roman", "TradeGothic"], referencePath: templatePath, referenceSha256: templateSha256 },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "DELTA_h_SPENDWISE_SIH2026_v5.validation.json"),
});
console.log(JSON.stringify(result));
