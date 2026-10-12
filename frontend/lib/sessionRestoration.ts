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

    // Reconstruct persisted tool execution runs so they survive refresh and precede the final answer
    const toolRecs = vis.tool_records || vis.toolRecords;
    if (toolRecs && Array.isArray(toolRecs) && toolRecs.length > 0) {
      for (const tr of toolRecs) {
        const tName = tr.tool_name || tr.name || "tool";
        const isDelegation = tName.toLowerCase().includes("delegate") || tName.toLowerCase().includes("subagent");
        if (isDelegation) {
          const args = tr.tool_args || {};
          const subGoal = args.goal || args.title || tr.detail || "Delegated Mission";
          restored.push({
            speaker: "output",
            text: "",
            visualType: "subagent",
            subagentData: {
              delegationId: `del_${tr.checkpoint_id || Date.now()}`,
              goal: subGoal,
              status: "completed",
              tasks: [
                {
                  id: `task_${tr.checkpoint_id || "1"}`,
                  taskId: `task_${tr.checkpoint_id || "1"}`,
                  goal: subGoal,
                  model: args.model || vis.model || vis.model_id,
                  status: "completed",
                  depth: 1,
                  startedAt: Date.now(),
                  activity: [tr.action_title || `Completed ${tName}`],
                  summary: tr.summary || "Completed",
                  findings: typeof tr.raw_result === "string" ? tr.raw_result : (tr.summary || "Completed"),
                }
              ]
            },
            agentMode: (vis.agent_mode || vis.agentMode || "build") as "plan" | "build",
            modelId: vis.model || vis.model_id || vis.modelId,
          });
          continue;
        }

        restored.push({
          speaker: "output",
          text: "",
          visualType: "agent_action",
          agentActionData: {
            eventType: "agent_action_complete",
            toolName: tName,
            actionTitle: `Completed ${tName}`,
            summary: tr.summary || "Done",
            detail: tr.detail || (tr.tool_args?.query ? `Query: ${tr.tool_args.query}` : tr.summary || ""),
            rawResult: tr.raw_result || tr.summary || "",
            filePath: tr.file_path || tr.tool_args?.file_path || tr.tool_args?.path,
            filename: tr.filename || tr.tool_args?.filename,
            command: tr.command || tr.tool_args?.command,
            query: tr.query || tr.tool_args?.query,
            toolArgs: tr.tool_args,
            status: "done",
          },
          agentMode: (vis.agent_mode || vis.agentMode || "build") as "plan" | "build",
          modelId: vis.model || vis.model_id || vis.modelId,
        });
      }
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
