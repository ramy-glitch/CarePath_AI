function rangeText(range) {
  if (!range) return "Not printed";
  return `${range.low}–${range.high}`;
}

function pill(card) {
  if (card.urgent) return "Needs attention today";
  if (card.band === "implausible") return "Not interpreted";
  if (card.band === "low") return "Below the range used";
  if (card.band === "high") return "Above the range used";
  if (card.band === "normal") return "Within the range used";
  return "No range to compare";
}

export function renderCards(container, cards) {
  container.replaceChildren();
  for (const card of cards) {
    const article = document.createElement("article");
    article.className = `card band-${card.band}`;
    const title = document.createElement("h3");
    title.textContent = card.testName;
    const badge = document.createElement("p");
    badge.className = "pill";
    badge.textContent = pill(card);
    const result = document.createElement("p");
    result.className = "result-line";
    result.textContent = `${card.value} ${card.unit}`;
    const ranges = document.createElement("dl");
    ranges.className = "ranges";
    ranges.append(pair("Range on the report", rangeText(card.reportRange)));
    ranges.append(pair("Range used", rangeText(card.usedRange)));
    const why = document.createElement("p");
    why.textContent = card.usedBecause;
    const heading = document.createElement("h4");
    heading.textContent = card.title;
    const body = document.createElement("p");
    body.textContent = card.text;
    article.append(title, badge, result, ranges, why, heading, body);
    if (typeof card.sourceUrl === "string" && card.sourceUrl.startsWith("https://")) {
      const source = document.createElement("p");
      source.className = "fine";
      const link = document.createElement("a");
      link.href = card.sourceUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Placeholder link";
      source.append(
        document.createTextNode("From the patient library. "),
        link,
        document.createTextNode(" is not an NHS page."),
      );
      article.append(source);
    }
    container.append(article);
  }
}

function pair(label, value) {
  const wrap = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = value;
  wrap.append(term, detail);
  return wrap;
}

export function renderUncertainties(container, items) {
  container.replaceChildren();
  if (!items.length) {
    container.hidden = true;
    return;
  }
  container.hidden = false;
  const heading = document.createElement("h3");
  heading.textContent = "What CarePath isn't sure about";
  const list = document.createElement("ul");
  for (const item of items) {
    const line = document.createElement("li");
    line.textContent = item;
    list.append(line);
  }
  container.append(heading, list);
}
