import { deleteRecord, getAllRecords } from "./indexed-db.js";

export async function deleteFile(id) {
  await deleteRecord(id);
  const remaining = await getAllRecords();
  return remaining.every((record) => record.id !== id);
}

export async function countFiles() {
  const records = await getAllRecords();
  return records.length;
}
