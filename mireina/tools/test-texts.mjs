// Unit checks of check-texts.mjs (the font rules of the scrolling text screens). Run: node mireina/tools/test-texts.mjs
import assert from "node:assert/strict";
import { checkScrollingText, renderScrollingText } from "./check-texts.mjs";

let passed = 0;
function test(name, fn) {
  fn();
  passed++;
  console.log(`ok · ${name}`);
}

test("a clean text passes: letters of both cases, digits, the six marks, blank lines, final tilde", () => {
  const text = "FELICIDADES mi reina.\n\nlinea 2, con 123!\n\n~\n";
  assert.deepEqual(checkScrollingText(text), []);
});

test("accents, ñ, apostrophes and slashes are reported with their line; the hyphen is tolerated", () => {
  const problems = checkScrollingText("tenía\nniña\n1995-2000\nl'amour\ngithub.com/jorio\n~\n");
  assert.deepEqual(
    problems.map((p) => [p.line, p.chars.join("")]),
    [
      [1, "í"],
      [2, "ñ"],
      [4, "'"],
      [5, "/"],
    ],
    "the hyphen of 1995-2000 is tolerated like in the original credits",
  );
});

test("lines longer than 32 characters are reported", () => {
  const long = "a".repeat(33);
  const problems = checkScrollingText(`ok\n${long}\n~\n`);
  assert.equal(problems.length, 1);
  assert.equal(problems[0].line, 2);
  assert.match(problems[0].message, /33/);
});

test("the tilde must be the last non-blank character, exactly once", () => {
  assert.equal(checkScrollingText("hola\n").length, 1, "missing tilde");
  assert.equal(checkScrollingText("ho~la\n~\n").length, 1, "tilde inside the text");
});

test("renderScrollingText: normalises line endings, trims trailing blanks, appends the tilde", () => {
  assert.equal(renderScrollingText("uno\r\ndos\n\n\n"), "uno\ndos\n\n\n\n~\n");
  assert.equal(renderScrollingText("uno\ndos\n~"), "uno\ndos\n\n\n\n~\n");
});

console.log(`\n${passed} checks passed`);
