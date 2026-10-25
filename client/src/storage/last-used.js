export const RETENTION_MS = 24 * 60 * 60 * 1000;

export function stamp(at = Date.now()) {
  return at;
}

export function isExpired(lastUsed, at = Date.now()) {
  return typeof lastUsed !== "number" || at - lastUsed > RETENTION_MS;
}
