/** Remove passage records from a turn so they cannot be written into the saved transcript. */
export function discardPassages(turn) {
  if (turn && Object.prototype.hasOwnProperty.call(turn, "passages")) {
    delete turn.passages;
  }
  return turn;
}
