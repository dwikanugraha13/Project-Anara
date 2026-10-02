/**
 * transcriptStream.ts — Utility functions for real-time progressive transcript delta assembly
 * and sentence boundary reconciliation for Project Anara.
 */

export function mergeTranscriptText(existing: string, incoming: string): string {
  const ex = existing.trim();
  const inc = incoming.trim();
  if (!ex) return incoming;
  if (!inc) return existing;

  const exLower = ex.toLowerCase();
  const incLower = inc.toLowerCase();

  // 1. If incoming progressive STT refinement starts with existing, use incoming
  if (incLower.startsWith(exLower)) return incoming;

  // 2. If existing already contains incoming at the end, keep existing
  if (exLower.endsWith(incLower)) return existing;

  // 3. If incoming shares a full word prefix with existing (progressive revision)
  const exWords = ex.split(/\s+/);
  const incWords = inc.split(/\s+/);
  if (incWords.length >= exWords.length) {
    let allPrefixMatch = true;
    for (let i = 0; i < exWords.length; i++) {
      if (exWords[i].toLowerCase() !== incWords[i].toLowerCase()) {
        allPrefixMatch = false;
        break;
      }
    }
    if (allPrefixMatch) {
      return incoming;
    }
  }

  // 4. Otherwise append delta cleanly with space formatting
  return existing + (existing.endsWith(" ") || incoming.startsWith(" ") ? "" : " ") + incoming;
}
