const LOCK_NAME = "carepath-tab-lock";
const TAB_NAME = "carepath-tab-id";
const FRESH_MS = 5000;

export function tabId() {
  let id = sessionStorage.getItem(TAB_NAME);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(TAB_NAME, id);
  }
  return id;
}

export function readLock() {
  try {
    return JSON.parse(localStorage.getItem(LOCK_NAME) || "null");
  } catch {
    return null;
  }
}

export function otherTabIsOpen(at = Date.now()) {
  const lock = readLock();
  if (!lock || lock.tabId === tabId()) return false;
  return typeof lock.at === "number" && at - lock.at < FRESH_MS;
}

export function claimLock(at = Date.now()) {
  localStorage.setItem(LOCK_NAME, JSON.stringify({ tabId: tabId(), at }));
}

export function startLockHeartbeat() {
  claimLock();
  return setInterval(() => claimLock(), 2000);
}
