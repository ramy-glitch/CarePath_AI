const KEY_NAME = "carepath-aes-key";

export async function loadSessionKey() {
  const saved = sessionStorage.getItem(KEY_NAME);
  if (!saved) return null;
  const jwk = JSON.parse(saved);
  return crypto.subtle.importKey("jwk", jwk, { name: "AES-GCM" }, true, ["encrypt", "decrypt"]);
}

export async function createSessionKey() {
  const existing = await loadSessionKey();
  if (existing) return existing;
  const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
  const jwk = await crypto.subtle.exportKey("jwk", key);
  sessionStorage.setItem(KEY_NAME, JSON.stringify(jwk));
  return key;
}

export function destroySessionKey() {
  sessionStorage.removeItem(KEY_NAME);
}
