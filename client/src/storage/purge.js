import { deleteEveryRecord, deleteRecord } from "./indexed-db.js";
import { isExpired } from "./last-used.js";

export async function purgeExpired(records, at = Date.now()) {
  const removed = [];
  for (const record of records) {
    if (!isExpired(record.lastUsed, at)) continue;
    await deleteRecord(record.id);
    removed.push(record.id);
  }
  return removed;
}

export async function purgeUnreadable() {
  await deleteEveryRecord();
}
