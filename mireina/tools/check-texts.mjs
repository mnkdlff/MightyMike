// The font rules of the scrolling text screens (credits, win1, win3): the big font only has A-Z (multicolour),
// a-z (red), 0-9 and ! ? . : @ , — no accents, no ñ, no slash; the hyphen is tolerated — the screen is 32 letters wide
// (FONT_WIDTH 20 on 640 px) and the engine reads up to the first ~, which must therefore close the text.
// As a script it checks Data/System/*.txt and exits 1 on any problem: node mireina/tools/check-texts.mjs
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// The hyphen is tolerated: the original credits already carry "1995-2000" and the engine draws it as glyph 0.
export const ALLOWED = /[A-Za-z0-9 !?.:@,-]/;
export const MAX_COLS = 32;
export const FILES = ["credits.txt", "win1.txt", "win3.txt"];

/** Problems with a scrolling text: `{ line, chars, message }` per offending line; empty when the text is clean. */
export function checkScrollingText(text) {
  const problems = [];
  const normalized = text.replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const tilde = normalized.indexOf("~");
  if (tilde === -1) {
    problems.push({ line: lines.length, chars: [], message: "missing the final ~ (the engine reads up to it)" });
  } else if (normalized.slice(tilde + 1).trim() !== "") {
    const line = normalized.slice(0, tilde).split("\n").length;
    problems.push({ line, chars: ["~"], message: "~ inside the text: everything after it is never shown" });
  }
  const bodyLines = (tilde === -1 ? normalized : normalized.slice(0, tilde)).split("\n");
  bodyLines.forEach((line, i) => {
    const n = i + 1;
    const bad = [];
    for (const ch of line) if (!ALLOWED.test(ch) && ch !== "~" && !bad.includes(ch)) bad.push(ch);
    if (bad.length) problems.push({ line: n, chars: bad, message: `characters the font does not have: ${bad.join(" ")}` });
    if (line.length > MAX_COLS) problems.push({ line: n, chars: [], message: `${line.length} characters, the screen fits ${MAX_COLS}` });
  });
  return problems;
}

/** The file content for a text: LF endings, no trailing blanks or tilde, then four blank lines and the ~. */
export function renderScrollingText(text) {
  const body = text.replace(/\r\n/g, "\n").replace(/[\s~]+$/, "");
  return `${body}\n\n\n\n~\n`;
}

export function checkFiles(dataDir) {
  let failures = 0;
  for (const name of FILES) {
    const file = path.join(dataDir, name);
    if (!existsSync(file)) continue;
    const problems = checkScrollingText(readFileSync(file, "utf8"));
    for (const p of problems) {
      failures++;
      console.error(`${name}:${p.line}: ${p.message}`);
    }
    if (!problems.length) console.log(`ok · ${name}`);
  }
  return failures;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
  const failures = checkFiles(path.join(root, "Data", "System"));
  if (failures) {
    console.error(`${failures} problem(s)`);
    process.exit(1);
  }
}
