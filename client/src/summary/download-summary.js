function rangeText(range) {
  if (!range) return "not printed";
  return `${range.low}–${range.high}`;
}

function reading(card) {
  if (card.urgent) return "Fixed urgent notice";
  if (card.band === "implausible") return "Not interpreted";
  if (card.band === "low") return "Below the range used";
  if (card.band === "high") return "Above the range used";
  if (card.band === "normal") return "Within the range used";
  return "No range to compare";
}

export function buildSummary(prepared) {
  const lines = [
    "CarePath summary",
    "General information for a conversation with your GP. Not a diagnosis. No personal details are included.",
    "",
  ];
  for (const card of prepared.cards) {
    lines.push(card.testName);
    lines.push(`Result: ${card.value} ${card.unit}`);
    lines.push(`Range on the report: ${rangeText(card.reportRange)}`);
    lines.push(`Range used: ${rangeText(card.usedRange)}`);
    lines.push(`Why this range: ${card.usedBecause}`);
    lines.push(`Reading: ${reading(card)}`);
    lines.push("");
  }
  if (prepared.uncertainties.length) {
    lines.push("What CarePath is not sure about");
    for (const item of prepared.uncertainties) lines.push(`- ${item}`);
    lines.push("");
  }
  lines.push("Questions you could ask");
  for (const question of prepared.questions) lines.push(`- ${question}`);
  lines.push("");
  lines.push("This file was made in your browser. It was not sent to CarePath's server.");
  return lines.join("\n");
}

export function downloadSummary(prepared) {
  const text = buildSummary(prepared);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "carepath-summary.txt";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
