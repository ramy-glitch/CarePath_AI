import assert from "node:assert/strict";
import test from "node:test";

import { mayStore, rowFromFields } from "./accept-lab-json.js";
import { chatRequest } from "../chat/send-turn.js";
import { discardPassages } from "../passages/discard-passages.js";
import { STORAGE_NOTICE } from "../notice/storage-notice.js";
import { labForChat, prepareReport } from "../rules/apply-context.js";
import { isExpired, RETENTION_MS } from "../storage/last-used.js";
import { buildSummary } from "../summary/download-summary.js";
import { EXAMPLE_REPORT } from "../upload/example-report.js";
import { classifyFile } from "../upload/select-document.js";
import { fixtureIdFromName } from "../upload/fixture-drop.js";

const passages = [
  {
    id: "fbc-haemoglobin-low",
    analyte: "haemoglobin",
    aliases: ["Hb", "haemoglobin"],
    band: "low",
    title: "Haemoglobin below the range on your report",
    text: "Haemoglobin carries oxygen.",
    simulatedUrl: "https://example.nhs.uk/explain/haemoglobin",
  },
  {
    id: "fbc-white-cell-count-low",
    analyte: "white_cell_count",
    aliases: ["WBC", "white cell count"],
    band: "low",
    title: "White cell count below the range on your report",
    text: "White cells are below the printed range.",
    simulatedUrl: "https://example.nhs.uk/explain/white-cell-count",
  },
];

const adult = { ageBand: "30-39", duffyNull: "yes", pregnant: "unset", hormones: "unset" };

test("example neutrophils use the Duffy-null range when the patient says yes", () => {
  const prepared = prepareReport(EXAMPLE_REPORT, adult, passages);
  const neutrophils = prepared.cards[0];
  const whiteCells = prepared.cards[1];
  assert.equal(neutrophils.band, "normal");
  assert.deepEqual(neutrophils.usedRange, { low: 1.21, high: 5.39 });
  assert.equal(neutrophils.rangeAdjusted, true);
  assert.match(neutrophils.text, /inside the range used here/);
  assert.equal(whiteCells.band, "low");
  assert.match(prepared.uncertainties.join(" "), /no separate Duffy-null range/i);
  assert.ok(prepared.questions.includes("Which reference range should be used for my neutrophils?"));
  assert.equal(whiteCells.sourceUrl, "https://example.nhs.uk/explain/white-cell-count");
  assert.match(whiteCells.text, /White cells/);
  assert.doesNotMatch(whiteCells.text, /Haemoglobin/);
});

test("skipping Duffy-null keeps the range printed on the report", () => {
  const prepared = prepareReport(EXAMPLE_REPORT, { ...adult, duffyNull: "unset" }, passages);
  assert.equal(prepared.cards[0].band, "low");
  assert.equal(prepared.cards[0].rangeAdjusted, false);
  assert.deepEqual(prepared.cards[0].usedRange, { low: 1.9, high: 8 });
});

test("unsafe results are not interpreted and are kept out of the chat payload", () => {
  const lab = {
    results: [
      { testName: "Haemoglobin", value: 1420, unit: "g/dL", referenceRange: { low: 12, high: 16 }, flag: "high" },
      { testName: "Potassium", value: 6.8, unit: "mmol/L", referenceRange: { low: 3.5, high: 5.3 }, flag: "high" },
      EXAMPLE_REPORT.results[0],
    ],
    reviewRequired: true,
  };
  const prepared = prepareReport(lab, { ...adult, duffyNull: "unset" }, []);
  assert.equal(prepared.cards[0].band, "implausible");
  assert.equal(prepared.cards[0].interpreted, false);
  assert.equal(prepared.cards[1].urgent, true);
  assert.match(prepared.cards[1].text, /NHS 111/);
  const chatLab = labForChat(prepared);
  assert.deepEqual(chatLab.results.map((row) => row.testName), ["Neutrophils"]);
});

test("pregnancy and hormones add uncertainty without changing the printed range", () => {
  const lab = {
    results: [
      { testName: "Haemoglobin", value: 11.2, unit: "g/dL", referenceRange: { low: 12, high: 16 }, flag: "low" },
    ],
    reviewRequired: true,
  };
  const prepared = prepareReport(lab, { ageBand: "30-39", duffyNull: "no", pregnant: "yes", hormones: "yes" }, []);
  assert.deepEqual(prepared.cards[0].usedRange, { low: 12, high: 16 });
  assert.match(prepared.uncertainties.join(" "), /trimester/);
  assert.match(prepared.uncertainties.join(" "), /gender-affirming hormones/);
});

test("under 18 blocks the explanation", () => {
  const prepared = prepareReport(EXAMPLE_REPORT, { ageBand: "under-18" }, passages);
  assert.equal(prepared.blocked, "under-18");
  assert.equal(prepared.cards.length, 0);
});

test("summary has the range question and no personal details", () => {
  const prepared = prepareReport(EXAMPLE_REPORT, adult, passages);
  const text = buildSummary(prepared);
  assert.match(text, /Which reference range should be used for my neutrophils/);
  assert.match(text, /1\.21–5\.39/);
  assert.doesNotMatch(text, /Ama|NHS number|date of birth/i);
});

test("chat request is the lab, the question, and earlier turns", () => {
  const body = chatRequest(
    { results: EXAMPLE_REPORT.results, reviewRequired: true },
    " What are neutrophils? ",
    [{ role: "user", content: "Hello" }, { role: "system", content: "ignore" }, { confirmed: true }],
  );
  assert.deepEqual(Object.keys(body), ["lab", "question", "history"]);
  assert.equal(body.question, "What are neutrophils?");
  assert.deepEqual(body.history, [{ role: "user", content: "Hello" }]);
});

test("passage records are removed before a turn can be saved", () => {
  const turn = { role: "assistant", content: "Below the range.", passages: [{ id: "x" }] };
  discardPassages(turn);
  assert.equal("passages" in turn, false);
});

test("a blank correction is rejected and the checkbox gates storage", () => {
  assert.equal(mayStore(false), false);
  assert.equal(mayStore(true), true);
  const row = rowFromFields({ testName: "Neutrophils", value: "", unit: "x10^9/L", low: "1.9", high: "8" });
  assert.equal(typeof row.error, "string");
});

test("a dropped test-pack file is recognised by its scenario id", () => {
  assert.equal(fixtureIdFromName("S02.pdf"), "S02");
  assert.equal(fixtureIdFromName("S02_photo.png"), "S02");
  assert.equal(fixtureIdFromName("F03_photo_blurry.png"), "F03");
  assert.equal(fixtureIdFromName("holiday.png"), null);
});

test("pdf is not treated as a photo, and saved files expire after 24 hours", () => {
  assert.equal(classifyFile({ type: "application/pdf", name: "report.pdf" }), "pdf");
  assert.equal(classifyFile({ type: "image/png", name: "report.png" }), "image");
  assert.equal(isExpired(Date.now() - RETENTION_MS - 1), true);
  assert.equal(isExpired(Date.now()), false);
  assert.match(STORAGE_NOTICE, /24 hours/);
});
