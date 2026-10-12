export type ConnectionStatus = "connected" | "connecting" | "disconnected" | "error";

export type ConnectionScope = "all" | "default" | "architect" | "backend" | "frontend" | "tester";

export type ConnectionFilter = "all" | "connected" | "inactive";

export interface ConnectionPlatform {
  id: string;
  name: string;
  category: "chat" | "collaboration" | "social" | "developer" | "media";
  description: string;
  status: ConnectionStatus;
  enabled: boolean;
  appliesTo: ConnectionScope[];
  quickSetupAvailable?: boolean;
  quickSetupText?: string;
  quickSetupActionText?: string;
  guideSteps?: string[];
  guideUrl?: string;
  requiredFields?: {
    key: string;
    label: string;
    placeholder: string;
    type?: "text" | "password";
    helperText?: string;
  }[];
  recommendedFields?: {
    key: string;
    label: string;
    placeholder: string;
    type?: "text" | "password" | "tags";
    helperText?: string;
  }[];
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}
