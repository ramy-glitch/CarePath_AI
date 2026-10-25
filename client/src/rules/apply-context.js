/**
 * Fixed range rules. The explanation model is not asked which range applies.
 * Duffy-null neutrophil bounds are the prototype figures from the project range notes: 1.21–5.39.
 */

import { URGENT_MESSAGE } from "../refusal/fixed-message.js";

export const DUFFY_NEUTROPHIL_RANGE = { low: 1.21, high: 5.39 };
export const POTASSIUM_URGENT_AT = 6.5;

const WHITE_CELL_NAMES = new Set([
  "wbc",
  "white cell count",
  "white blood cell count",
  "white blood cells",
  "white cells",
  "leukocytes",
  "leucocytes",
]);

const EXTRA_ALIASES = {
  white_cell_count: ["white blood cells", "white cells"],
};

export function normName(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function isNeutrophils(name) {
  const n = normName(name);
  return n === "neutrophils" || n === "neutrophil" || n === "neutrophil count" || n === "anc";
}

export function isWhiteCells(name) {
  return WHITE_CELL_NAMES.has(normName(name));
}

export function isPotassium(name) {
  return normName(name) === "potassium";
}

export function isHaemoglobin(name) {
  const n = normName(name);
  return n === "haemoglobin" || n === "hemoglobin" || n === "hb";
}

function haemoglobinScale(unit) {
  const compact = String(unit || "").toLowerCase().replace(/\s+/g, "");
  if (compact.includes("g/dl")) return "g/dL";
  if (compact.includes("g/l")) return "g/L";
  return "other";
}

export function implausibleHaemoglobin(row) {
  if (!isHaemoglobin(row.testName) || typeof row.value !== "number") return false;
  const scale = haemoglobinScale(row.unit);
  if (scale === "g/dL") return row.value > 25 || row.value < 2;
  if (scale === "g/L") return row.value > 250 || row.value < 20;
  return row.value >= 1000 || row.value <= 0;
}

export function urgentPotassium(row) {
  return isPotassium(row.testName) && typeof row.value === "number" && row.value >= POTASSIUM_URGENT_AT;
}

function bandFor(value, range) {
  if (!range || !(range.low < range.high)) return "unknown";
  if (value < range.low) return "low";
  if (value > range.high) return "high";
  return "normal";
}

function formatRange(range) {
  if (!range) return "not printed";
  return `${range.low}–${range.high}`;
}

function statusLine(band) {
  if (band === "low") return "Below the range used";
  if (band === "high") return "Above the range used";
  if (band === "normal") return "Within the range used";
  return "No range to compare";
}

function matchPassage(passages, testName, band) {
  const needle = normName(testName);
  return (passages || []).find((passage) => {
    if (passage.band !== band) return false;
    const names = [
      passage.analyte.replaceAll("_", " "),
      ...(passage.aliases || []),
      ...(EXTRA_ALIASES[passage.analyte] || []),
    ];
    return names.some((name) => normName(name) === needle);
  });
}

function adjustedCopy(card) {
  const where =
    card.band === "low" ? "below" : card.band === "high" ? "above" : card.band === "normal" ? "inside" : "compared with";
  return `${card.testName} are one type of white cell. Your result is ${card.value} ${card.unit}. The range on your report is ${formatRange(card.reportRange)}. The range used here is ${formatRange(card.usedRange)}, because you said a doctor has told you that you have the Duffy-null blood type. That result sits ${where} the range used here. This is general information. It is not a diagnosis, and it does not say what should happen next.`;
}

function fallbackCopy(card) {
  return `${card.testName}: your result is ${card.value} ${card.unit}. ${statusLine(card.band)}. CarePath has no library passage for this test and band. This is general information, not a diagnosis.`;
}

function buildCard(row, context, passages) {
  const reportRange = row.referenceRange;
  const card = {
    testName: row.testName,
    value: row.value,
    unit: row.unit,
    reportRange,
    usedRange: reportRange,
    usedBecause: "The range printed on your report.",
    rangeAdjusted: false,
    band: row.flag === "low" || row.flag === "high" || row.flag === "normal" ? row.flag : bandFor(row.value, reportRange),
    interpreted: true,
    urgent: false,
    uncertainties: [],
    title: row.testName,
    text: "",
    sourceUrl: null,
    sourceTitle: null,
  };

  if (implausibleHaemoglobin(row)) {
    card.interpreted = false;
    card.band = "implausible";
    card.usedRange = null;
    card.usedBecause = "No range was applied.";
    card.title = "Number not interpreted";
    card.text =
      "This number does not look like a haemoglobin result CarePath can read. It may be a printing error. CarePath will not interpret it.";
    return card;
  }

  if (urgentPotassium(row)) {
    card.interpreted = false;
    card.urgent = true;
    card.band = "urgent";
    card.usedRange = reportRange;
    card.usedBecause = "A fixed rule for a high potassium result. The explanation model is not asked.";
    card.title = "Potassium needs attention today";
    card.text = URGENT_MESSAGE;
    return card;
  }

  if (context.duffyNull === "yes" && isNeutrophils(row.testName)) {
    card.usedRange = DUFFY_NEUTROPHIL_RANGE;
    card.usedBecause = "You said a doctor has told you that you have the Duffy-null blood type. CarePath did not infer this.";
    card.rangeAdjusted = true;
    card.band = bandFor(row.value, card.usedRange);
  } else {
    card.band = bandFor(row.value, reportRange);
  }

  if (context.duffyNull === "yes" && isWhiteCells(row.testName) && card.band === "low") {
    card.uncertainties.push(
      "Your white cell count is still below the range on your report. CarePath has no separate Duffy-null range for the white cell count.",
    );
  }

  if (context.pregnant === "yes" && isHaemoglobin(row.testName)) {
    card.uncertainties.push(
      "You said you are pregnant. CarePath has not replaced the haemoglobin range, because the threshold depends on the trimester.",
    );
  }

  if (card.rangeAdjusted) {
    card.title = `${card.testName} against the range used for you`;
    card.text = adjustedCopy(card);
    return card;
  }

  const passage = matchPassage(passages, card.testName, card.band);
  if (passage) {
    card.title = passage.title;
    card.text = passage.text;
    card.sourceUrl = passage.simulatedUrl;
    card.sourceTitle = passage.title;
    return card;
  }

  card.title = statusLine(card.band);
  card.text = fallbackCopy(card);
  return card;
}

export function questionsFor(cards, context) {
  const questions = [];
  if (context.duffyNull === "yes" && cards.some((card) => isNeutrophils(card.testName))) {
    questions.push("Which reference range should be used for my neutrophils?");
  }
  if (context.pregnant === "yes") {
    questions.push("Which haemoglobin threshold applies in this pregnancy?");
  }
  if (context.hormones === "yes") {
    questions.push("Which reference range should be used if I am taking gender-affirming hormones?");
  }
  if (cards.some((card) => card.band === "implausible")) {
    questions.push("Could this haemoglobin value be a printing error?");
  }
  if (!questions.length) questions.push("Do any of these results need to be looked at again?");
  return questions;
}

export function prepareReport(lab, context, passages = []) {
  const choice = context || {};
  if (choice.ageBand === "under-18") {
    return { blocked: "under-18", cards: [], uncertainties: [], questions: [] };
  }
  const cards = (lab?.results || []).map((row) => buildCard(row, choice, passages));
  const uncertainties = [];
  if (choice.hormones === "yes") {
    uncertainties.push(
      "You said you take gender-affirming hormones. CarePath has not changed any range because of that. Ask your GP which range should be used.",
    );
  }
  for (const card of cards) uncertainties.push(...card.uncertainties);
  return {
    blocked: null,
    cards,
    uncertainties,
    questions: questionsFor(cards, choice),
  };
}

export function labForChat(prepared) {
  const results = (prepared?.cards || [])
    .filter((card) => card.interpreted && !card.urgent && card.band !== "implausible")
    .map((card) => ({
      testName: card.testName,
      value: card.value,
      unit: card.unit,
      referenceRange: card.usedRange,
      flag: card.band === "low" || card.band === "high" || card.band === "normal" ? card.band : "unknown",
    }));
  if (!results.length) return null;
  return { results, reviewRequired: true };
}

export function mentionsPotassium(question) {
  return normName(question).includes("potassium");
}
