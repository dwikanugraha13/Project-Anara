"use client";

import React from "react";

export function ConnectionIcon({
  name,
  className = "w-5 h-5",
}: {
  name: string;
  className?: string;
}) {
  const n = (name || "").toLowerCase().trim();

  // Telegram
  if (n === "telegram" || n === "tg") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.37.74-.56 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
      </svg>
    );
  }

  // Discord
  if (n === "discord") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
      </svg>
    );
  }

  // Slack
  if (n === "slack") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
      </svg>
    );
  }

  // WhatsApp
  if (n === "whatsapp" || n === "wa") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91C2.13 13.66 2.59 15.36 3.45 16.86L2.05 22L7.3 20.62C8.75 21.41 10.38 21.83 12.04 21.83C17.5 21.83 21.95 17.38 21.95 11.92C21.95 9.27 20.92 6.78 19.05 4.91C17.18 3.03 14.69 2 12.04 2M12.05 3.67C14.25 3.67 16.31 4.53 17.87 6.09C19.42 7.65 20.28 9.72 20.28 11.92C20.28 16.46 16.58 20.15 12.04 20.15C10.56 20.15 9.11 19.76 7.85 19L7.55 18.83L4.43 19.65L5.26 16.61L5.06 16.29C4.24 15 3.8 13.47 3.8 11.91C3.81 7.37 7.5 3.67 12.05 3.67M9.53 7.03C9.36 7.03 9.08 7.09 8.84 7.35C8.6 7.61 7.92 8.25 7.92 9.55C7.92 10.85 8.87 12.11 9 12.28C9.13 12.45 10.87 15.14 13.53 16.29C14.16 16.57 14.66 16.73 15.04 16.85C15.68 17.06 16.26 17.03 16.72 16.96C17.24 16.88 18.31 16.31 18.53 15.67C18.76 15.03 18.76 14.49 18.69 14.37C18.62 14.26 18.45 14.19 18.19 14.07C17.93 13.94 16.66 13.31 16.42 13.22C16.18 13.14 16.01 13.1 15.84 13.35C15.67 13.61 15.18 14.19 15.03 14.36C14.88 14.53 14.73 14.55 14.47 14.42C14.21 14.3 13.38 14.03 12.39 13.15C11.62 12.46 11.1 11.61 10.95 11.35C10.8 11.09 10.93 10.95 11.06 10.82C11.18 10.7 11.33 10.51 11.47 10.34C11.61 10.17 11.66 10.04 11.75 9.87C11.84 9.7 11.79 9.55 11.73 9.42C11.67 9.3 11.18 8.1 10.97 7.62C10.77 7.14 10.57 7.21 10.42 7.2C10.28 7.2 10.11 7.2 9.94 7.2L9.53 7.03Z" />
      </svg>
    );
  }

  // Google Workspace
  if (n === "google" || n === "google workspace" || n === "workspace" || n === "gmail") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm3.6 15.8L12 15l-3.6 2.8 1.4-4.6-3.8-2.8h4.6L12 6l1.4 4.4h4.6l-3.8 2.8 1.4 4.6z" />
      </svg>
    );
  }

  // Spotify
  if (n === "spotify") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.586 14.424a.625.625 0 0 1-.86.208c-2.355-1.439-5.32-1.765-8.813-.967a.625.625 0 1 1-.28-1.22c3.818-.874 7.106-.504 9.745 1.118a.625.625 0 0 1 .208.861zm1.226-2.726a.782.782 0 0 1-1.077.257c-2.695-1.657-6.806-2.136-9.994-1.168a.782.782 0 0 1-.456-1.498c3.639-1.105 8.18-.574 11.27 1.332a.782.782 0 0 1 .257 1.077zm.106-2.833C14.69 8.92 9.388 8.744 6.305 9.68a.937.937 0 1 1-.546-1.792c3.535-1.073 9.4-0.865 13.14 1.356a.937.937 0 1 1-.98 1.621z" />
      </svg>
    );
  }

  // Mattermost
  if (n === "mattermost") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 14.5c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V10c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5v6.5zm-5-3c0 .83-.67 1.5-1.5 1.5S5 14.33 5 13.5V11c0-.83.67-1.5 1.5-1.5S8 10.17 8 11v2.5zm10 0c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V11c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5v2.5z" />
      </svg>
    );
  }

  // Matrix
  if (n === "matrix") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 4h3v16H4M20 4h-3v16h3M8 9l4 3-4 3M16 15l-4-3 4-3" />
      </svg>
    );
  }

  // Signal
  if (n === "signal") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.477 2 2 6.477 2 12c0 1.84.498 3.565 1.365 5.048L2.1 21.9l4.982-1.238A9.957 9.957 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2zm0 18a7.96 7.96 0 01-4.14-1.157l-.3-.178-3.078.766.78-2.997-.197-.315A7.968 7.968 0 014 12c0-4.411 3.589-8 8-8s8 3.589 8 8-3.589 8-8 8z" />
      </svg>
    );
  }

  // BlueBubbles
  if (n === "bluebubbles") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <circle cx="9" cy="12" r="6" />
        <circle cx="16" cy="10" r="4.5" />
      </svg>
    );
  }

  // Email
  if (n === "email") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    );
  }

  // SMS / Twilio
  if (n === "sms" || n.includes("twilio")) {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    );
  }

  // Google Chat
  if (n === "google chat" || n === "googlechat") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z" />
      </svg>
    );
  }

  // DingTalk
  if (n === "dingtalk") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
      </svg>
    );
  }

  // Feishu / Lark
  if (n === "feishu" || n === "lark") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 3L2 12h3v8h14v-8h3L12 3zm0 3.7l6 5.4V18H6v-5.9l6-5.4z" />
      </svg>
    );
  }

  // WeCom / WeChat
  if (n === "wecom" || n === "wechat") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M8.5 4C4.91 4 2 6.57 2 9.75c0 1.83.99 3.46 2.54 4.51L3.8 17.1l3.05-1.52c.53.11 1.08.17 1.65.17.27 0 .53-.02.79-.05-.29-.6-.44-1.25-.44-1.95 0-3.18 2.91-5.75 6.5-5.75.24 0 .47.02.7.04C15.22 5.72 12.12 4 8.5 4zm8.5 5.5c-3.04 0-5.5 2.13-5.5 4.75 0 2.63 2.46 4.75 5.5 4.75.49 0 .96-.06 1.41-.16l2.59 1.29-.67-2.43c1.32-.89 2.17-2.14 2.17-3.45 0-2.62-2.46-4.75-5.5-4.75z" />
      </svg>
    );
  }

  // QQ Bot
  if (n === "qq" || n === "qq bot" || n === "qqbot") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="12" r="9" />
        <path d="M9 10h.01M15 10h.01M9.5 15a3.5 3.5 0 005 0" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" />
      </svg>
    );
  }

  // Yuanbao
  if (n === "yuanbao") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
      </svg>
    );
  }

  // API Server
  if (n === "api server" || n === "apiserver" || n === "api") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
      </svg>
    );
  }

  // Webhooks
  if (n === "webhooks" || n === "webhook") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
      </svg>
    );
  }

  // A2A (Agent-to-Agent)
  if (n === "a2a" || n === "agent to agent") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
      </svg>
    );
  }

  // Buzz
  if (n === "buzz") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    );
  }

  // Fallback
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="9" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01" />
    </svg>
  );
}
