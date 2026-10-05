import type { SessionMessage } from "@/hooks/websocketTypes";
import type { TranscriptItem } from "@/components/workbench/types";

/**
 * Parses raw SQLite/WebSocket session message history into structured visual transcript items.
 * Standard across Anara Code Studio and Anara Companion Workbench.
 */
export function restoreTranscriptFromMessages(messages: SessionMessage[]): TranscriptItem[] {
  if (!messages || !Array.isArray(messages)) return [];

  const restored: TranscriptItem[] = [];
  for (const m of messages) {
    const u = (m.user_text || "").trim();
    const a = (m.ai_text || "").trim();
    const vis = m.visual_data || {};

    if (u) {
      restored.push({ speaker: "input", text: u });
    }

    const hasValidVisual = Boolean(vis.visualType && vis.visualType !== "none");
    if (a || hasValidVisual || m.media_type) {
      restored.push({
        speaker: "output",
        text: a,
        visualType: hasValidVisual ? vis.visualType : (m.media_type as any),
        imageUrl: vis.imageUrl || m.media_url,
        imageTitle: vis.imageTitle,
        sourceDomain: vis.sourceDomain,
        sourceUrl: vis.sourceUrl,
        images: vis.images,
        weatherData: vis.weatherData,
        codeData: vis.codeData,
        systemHudData: vis.systemHudData,
        knowledgeCardData: vis.knowledgeCardData,
        todoData: vis.todoData,
        briefingData: vis.briefingData,
        agentActionData: vis.agentActionData,
        documentViewerData: vis.documentViewerData,
        workspaceFolderData: vis.workspaceFolderData,
        planData: vis.planData,
        mediaType: m.media_type as any,
        agentMode: (vis.agent_mode || vis.agentMode || "build") as "plan" | "build",
        modelId: vis.model || vis.model_id || vis.modelId,
        durationText: vis.duration_text || vis.durationText || (vis.duration ? `${Math.round(vis.duration)}s` : undefined),
        tokenUsage: vis.tokenUsage || vis.token_usage,
        toolsUsed: vis.tools_used || vis.toolsUsed || vis.token_usage?.tools_used || vis.tokenUsage?.toolsUsed,
        toolRecordsCount: vis.tool_records_count || vis.toolRecordsCount,
      });
    }
  }

  return restored;
}
