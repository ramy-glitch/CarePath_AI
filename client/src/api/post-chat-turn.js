export async function postChatTurn(body) {
  let response;
  try {
    response = await fetch("/chat", {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    const error = new Error("unreachable");
    error.reason = "unreachable";
    throw error;
  }
  if (!response.ok) {
    const error = new Error("rejected");
    error.reason = response.status === 503 ? "unavailable" : "rejected";
    throw error;
  }
  return response.json();
}
