const MAX_BYTES = 5 * 1024 * 1024;

export function classifyFile(file) {
  if (!file) return "rejected";
  const type = (file.type || "").toLowerCase();
  if (type === "image/png" || type === "image/jpeg" || type === "image/jpg") return "image";
  const name = (file.name || "").toLowerCase();
  if (type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  return "rejected";
}

export function sizeProblem(file) {
  if (!file || file.size === 0) return "empty";
  if (file.size > MAX_BYTES) return "large";
  return null;
}
