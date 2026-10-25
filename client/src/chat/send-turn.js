export function chatRequest(lab, question, transcript) {
  const history = (transcript || [])
    .slice(-20)
    .filter((turn) => turn && (turn.role === "user" || turn.role === "assistant") && typeof turn.content === "string")
    .map((turn) => ({ role: turn.role, content: turn.content.slice(0, 4000) }));
  return {
    lab,
    question: question.trim(),
    history,
  };
}

export function rememberTurn(transcript, role, content) {
  const next = transcript.concat([{ role, content }]);
  return next.slice(-20);
}
