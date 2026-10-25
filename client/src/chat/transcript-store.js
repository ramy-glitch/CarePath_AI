/** Transcript entries are role and content only. Passages are not part of the saved chat. */
export function emptyTranscript() {
  return [];
}

export function appendTurn(transcript, role, content) {
  return transcript.concat([{ role, content }]).slice(-20);
}
