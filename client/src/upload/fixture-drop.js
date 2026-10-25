const ID_PATTERN = /^([SF]\d{2})/i;

export function fixtureIdFromName(name) {
  const base = String(name || "").split(/[/\\]/).pop();
  const match = ID_PATTERN.exec(base);
  return match ? match[1].toUpperCase() : null;
}

export async function fetchCatalog() {
  const response = await fetch("/fixtures");
  if (!response.ok) return [];
  const body = await response.json();
  return Array.isArray(body.fixtures) ? body.fixtures : [];
}

export async function fetchFixture(id) {
  const response = await fetch(`/fixtures/${id}`);
  if (response.status === 422) {
    const error = new Error("unreadable");
    error.reason = "unreadable";
    throw error;
  }
  if (!response.ok) {
    const error = new Error("rejected");
    error.reason = "rejected";
    throw error;
  }
  return response.json();
}
