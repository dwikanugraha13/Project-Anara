"use client";

import React from "react";
import ConnectionsWorkspaceView, {
  ConnectionsWorkspaceViewProps,
} from "@/components/connections/ConnectionsWorkspaceView";

export type MessagingWorkspaceViewProps = ConnectionsWorkspaceViewProps;

export default function MessagingWorkspaceView({ onClose }: MessagingWorkspaceViewProps) {
  return <ConnectionsWorkspaceView onClose={onClose} />;
}

