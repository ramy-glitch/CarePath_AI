export function renderPassages(passages) {
  if (!passages || !passages.length) return null;
  const block = document.createElement("div");
  block.className = "sources";
  const heading = document.createElement("p");
  heading.className = "who";
  heading.textContent = "Sources for this reply";
  const note = document.createElement("p");
  note.className = "fine";
  note.textContent = "Shown with this reply, then not saved. Links are placeholders, not NHS pages.";
  const list = document.createElement("ul");
  for (const passage of passages) {
    const item = document.createElement("li");
    const title = document.createElement("p");
    title.textContent = passage.title || passage.id;
    item.append(title);
    if (passage.text) {
      const body = document.createElement("p");
      body.textContent = passage.text;
      item.append(body);
    }
    if (typeof passage.simulatedUrl === "string" && passage.simulatedUrl.startsWith("https://")) {
      const link = document.createElement("a");
      link.href = passage.simulatedUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = passage.simulatedUrl;
      item.append(link);
    }
    list.append(item);
  }
  block.append(heading, note, list);
  return block;
}
