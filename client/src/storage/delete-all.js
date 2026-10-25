import { destroySessionKey } from "./session-key.js";
import { countFiles } from "./delete-file.js";
import { purgeUnreadable } from "./purge.js";

export async function deleteAll() {
  await purgeUnreadable();
  destroySessionKey();
  const remaining = await countFiles();
  return remaining === 0;
}
