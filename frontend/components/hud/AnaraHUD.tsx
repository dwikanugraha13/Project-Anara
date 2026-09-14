"use client";

import React from "react";
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
  HudWhatsAppQrCard,
  HudWhatsAppChatCard,
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
  if (visualType === "plan_card" && planData) {
    return (
      <HudPlanCard
        planData={planData}
        onApprovePlan={onApprovePlan}
        onRejectPlan={onRejectPlan}
        onOpenFile={onOpenFile}
        onDismiss={onDismiss}
      />
    );
  }

  if ((visualType === "document_viewer" && documentViewerData) || (visualType === "folder_workspace" && workspaceFolderData)) {
    return (
      <HudDocumentViewer
        documentViewerData={documentViewerData}
        workspaceFolderData={workspaceFolderData}
        onOpenFile={onOpenFile}
        onDismiss={onDismiss}
      />
    );
  }

  if (visualType === "image" && (imageUrl || (images && images.length > 0))) {
    return (
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
  }

  if (visualType === "briefing" && briefingData) {
    return <HudBriefingCard briefingData={briefingData} onDismiss={onDismiss} />;
  }

  if (visualType === "weather" && weatherData) {
    return <HudWeatherCard weatherData={weatherData} onDismiss={onDismiss} />;
  }

  if (visualType === "code" && codeData) {
    return <HudCodeCard codeData={codeData} onDismiss={onDismiss} />;
  }

  if (visualType === "system_hud" && systemHudData) {
    return <HudSystemCard systemHudData={systemHudData} onDismiss={onDismiss} />;
  }

  if (visualType === "knowledge_card" && knowledgeCardData) {
    return <HudKnowledgeCard knowledgeCardData={knowledgeCardData} onDismiss={onDismiss} />;
  }

  if (visualType === "todo_list" && todoData && todoData.items) {
    return <HudTodoListCard todoData={todoData} onDismiss={onDismiss} />;
  }

  if (visualType === "agent_action" && agentActionData) {
    return <HudAgentActionCard agentActionData={agentActionData} onOpenFile={onOpenFile} onDismiss={onDismiss} />;
  }

  if (visualType === "whatsapp_qr") {
    return <HudWhatsAppQrCard imageUrl={imageUrl} onDismiss={onDismiss} />;
  }

  if (visualType === "whatsapp_chat" && knowledgeCardData) {
    return <HudWhatsAppChatCard knowledgeCardData={knowledgeCardData} onDismiss={onDismiss} />;
  }

  return null;
}
