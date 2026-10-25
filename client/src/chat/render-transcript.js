function bubble(role, content) {
  const item = document.createElement("li");
  item.className = role === "user" ? "bubble bubble-user" : "bubble";
  const who = document.createElement("p");
  who.className = "who";
  who.textContent = role === "user" ? "You" : "CarePath";
  const text = document.createElement("p");
  text.textContent = content;
  item.append(who, text);
  return item;
}

export function renderTranscript(list, turns) {
  list.replaceChildren();
  for (const turn of turns) {
    list.append(bubble(turn.role, turn.content));
  }
  return list;
}

export function appendBubble(list, role, content) {
  const item = bubble(role, content);
  list.append(item);
  return item;
}
