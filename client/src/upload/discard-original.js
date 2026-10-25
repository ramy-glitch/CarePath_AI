/** Drop the only in-memory handle to the original file. Nothing here is written to disk. */
export function discardOriginal(holder) {
  if (holder) holder.file = null;
}
