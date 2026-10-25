export async function requestAnonymisation(file) {
  const type = file.type === "image/jpg" ? "image/jpeg" : file.type;
  const bytes = await file.arrayBuffer();
  let response;
  try {
    response = await fetch("/api/v1/anonymise", {
      method: "POST",
      headers: { "content-type": type || "application/octet-stream" },
      body: bytes,
    });
  } catch {
    const error = new Error("unreachable");
    error.reason = "unreachable";
    throw error;
  }
  if (!response.ok) {
    const error = new Error("rejected");
    error.reason = response.status === 413 ? "large" : response.status === 422 ? "unreadable" : "rejected";
    throw error;
  }
  return response.json();
}
