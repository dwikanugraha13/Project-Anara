"use client";

import React, { useEffect } from "react";
import {
  WeatherData,
  CodeData,
  SystemHudData,
  KnowledgeCardData,
  BriefingData,
  TodoData,
  AgentActionData,
  DocumentViewerData,
  WorkspaceFolderData,
  PlanData,
  ImageItem,
  AnaraHUDProps,
} from "./types";

import HudPlanCard from "./HudPlanCard";
import HudDocumentViewer from "./HudDocumentViewer";
import HudImageGallery from "./HudImageGallery";
import HudBriefingCard from "./HudBriefingCard";
import {
  HudWeatherCard,
  HudCodeCard,
  HudSystemCard,
  HudKnowledgeCard,
  HudTodoListCard,
  HudAgentActionCard,
} from "./HudWidgets";

// Re-export all types for 100% backward compatibility
export type {
  WeatherData,
  CodeData,
  SystemHudData,
  KnowledgeCardData,
  BriefingData,
  TodoData,
  AgentActionData,
  DocumentViewerData,
  WorkspaceFolderData,
  PlanData,
  ImageItem,
  AnaraHUDProps,
};

export default function AnaraHUD({
  visualType = "image",
  imageUrl,
  imageTitle,
  sourceDomain,
  sourceUrl,
  imagePrompt,
  images,
  weatherData,
  codeData,
  systemHudData,
  knowledgeCardData,
  todoData,
  briefingData,
  agentActionData,
  documentViewerData,
  workspaceFolderData,
  planData,
  onOpenLightbox,
  onOpenFile,
  onApprovePlan,
  onRejectPlan,
  onDismiss,
}: AnaraHUDProps) {
  // Global Escape key listener to cleanly dismiss the HUD when requested
  // Wrapped with typable element guard and clean unmount to prevent orphaned listeners
  useEffect(() => {
    if (!onDismiss) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        const target = e.target as HTMLElement | null;
        if (target) {
          const tag = target.tagName;
          if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable) {
            return;
          }
        }
        e.preventDefault();
        onDismiss();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onDismiss]);

  if (visualType === "none") {
    return null;
  }

  let content: React.ReactNode = null;

  if (visualType === "plan_card" && planData) {
    content = (
      <HudPlanCard
        planData={planData}
        onApprovePlan={onApprovePlan}
        onRejectPlan={onRejectPlan}
        onOpenFile={onOpenFile}
        onDismiss={onDismiss}
      />
    );
  } else if (
    (visualType === "document_viewer" && documentViewerData) ||
    (visualType === "folder_workspace" && workspaceFolderData)
  ) {
    content = (
      <HudDocumentViewer
        documentViewerData={documentViewerData}
        workspaceFolderData={workspaceFolderData}
        onOpenFile={onOpenFile}
        onDismiss={onDismiss}
      />
    );
  } else if (visualType === "image" && (imageUrl || (images && images.length > 0))) {
    content = (
      <HudImageGallery
        images={images}
        imageUrl={imageUrl}
        imageTitle={imageTitle}
        sourceDomain={sourceDomain}
        sourceUrl={sourceUrl}
        imagePrompt={imagePrompt}
        onOpenLightbox={onOpenLightbox}
        onDismiss={onDismiss}
      />
    );
  } else if (visualType === "briefing" && briefingData) {
    content = <HudBriefingCard briefingData={briefingData} onDismiss={onDismiss} />;
  } else if (visualType === "weather" && weatherData) {
    content = <HudWeatherCard weatherData={weatherData} onDismiss={onDismiss} />;
  } else if (visualType === "code" && codeData) {
    content = <HudCodeCard codeData={codeData} onDismiss={onDismiss} />;
  } else if (visualType === "system_hud" && systemHudData) {
    content = <HudSystemCard systemHudData={systemHudData} onDismiss={onDismiss} />;
  } else if (visualType === "knowledge_card" && knowledgeCardData) {
    content = <HudKnowledgeCard knowledgeCardData={knowledgeCardData} onDismiss={onDismiss} />;
  } else if (visualType === "todo_list" && todoData && todoData.items) {
    content = <HudTodoListCard todoData={todoData} onDismiss={onDismiss} />;
  } else if (visualType === "agent_action" && agentActionData) {
    content = <HudAgentActionCard agentActionData={agentActionData} onOpenFile={onOpenFile} onDismiss={onDismiss} />;
  }

  if (!content) return null;

  return (
    <div className="w-full relative transition-all duration-200 ease-out" data-hud-active={visualType}>
      {content}
    </div>
  );
}
