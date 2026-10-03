"use client";

import { anaraApi } from "@/lib/apiClient";

export interface ExportSessionOptions {
  sessionId: number | string;
  title?: string | null;
  format?: "json" | "markdown";
}

function sanitizeFilenamePart(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

export function generateSessionFilename(
  sessionId: number | string,
  title?: string | null,
  ext: "json" | "md" = "json"
): string {
  const titlePart = title ? sanitizeFilenamePart(title) : "";
  const idPart = sanitizeFilenamePart(String(sessionId)).slice(0, 8) || "session";
  const base = titlePart ? `${titlePart}-${idPart}` : `session-${idPart}`;
  return `${base}.${ext}`;
}

export async function exportSession({
  sessionId,
  title,
  format = "json",
}: ExportSessionOptions): Promise<boolean> {
  if (!sessionId) return false;

  try {
    const res = await anaraApi.sessions.get(sessionId);
    const messages = res?.messages || [];
    const sessionMeta = res?.session || {};

    let blob: Blob;
    let filename: string;

    if (format === "markdown") {
      filename = generateSessionFilename(sessionId, title || sessionMeta.title, "md");
      const sessionTitle = title || sessionMeta.title || `Session ${sessionId}`;
      const exportDate = new Date().toLocaleString();

      const lines: string[] = [
        `# ${sessionTitle}`,
        `*Exported from Project Anara on ${exportDate}*`,
        "",
        "---",
        "",
      ];

      for (const m of messages) {
        const role = m.role === "user" ? "User" : "Anara";
        const text = m.content || m.text || "";
        lines.push(`### ${role}`);
        lines.push("");
        lines.push(text.trim());
        lines.push("");
        lines.push("---");
        lines.push("");
      }

      blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    } else {
      filename = generateSessionFilename(sessionId, title || sessionMeta.title, "json");
      const payload = {
        exported_at: new Date().toISOString(),
        session_id: sessionId,
        title: title || sessionMeta.title || null,
        message_count: messages.length,
        session: sessionMeta,
        messages,
      };

      blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json;charset=utf-8",
      });
    }

    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);

    // Clean up blob URL immediately to prevent memory leaks (Anara Standard)
    setTimeout(() => {
      URL.revokeObjectURL(downloadUrl);
    }, 150);

    return true;
  } catch (err) {
    console.error("[SessionExport] Failed to export session:", err);
    return false;
  }
}

export default exportSession;
