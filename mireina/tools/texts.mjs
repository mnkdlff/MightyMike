// Writes the MiReina texts into the game data: mireina/texts.json (an export of the « Power Pete Textos »
// artifact, { itemId: text }) → Data/System/credits.txt, win1.txt and, when present, win3.txt. Every file is
// validated against the font rules afterwards; the script exits 1 on any problem. The strings that live in the
// C sources (SCORE label, settings captions) are patched in the code under MR_TXT, not here.
// Run: node mireina/tools/texts.mjs
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { checkFiles, renderScrollingText } from "./check-texts.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const texts = JSON.parse(readFileSync(path.join(root, "mireina", "texts.json"), "utf8"));
const dataDir = path.join(root, "Data", "System");

const MAP = { credits: "credits.txt", win1: "win1.txt", win3: "win3.txt" };
for (const [id, file] of Object.entries(MAP)) {
  const text = texts[id];
  if (typeof text !== "string" || !text.trim()) {
    console.log(`-- · ${file} (no "${id}" text in texts.json, original kept)`);
    continue;
  }
  writeFileSync(path.join(dataDir, file), renderScrollingText(text));
  console.log(`wrote · ${file} (${text.split("\n").length} lines)`);
}

const failures = checkFiles(dataDir);
if (failures) {
  console.error(`${failures} problem(s): fix the text in the artifact, re-export, run again`);
  process.exit(1);
}
