"use client";

import HomePageClient from "./HomePageClient";

export default function Page() {
  return (
    <HomePageClient
      initialSidebarTab="history"
      initialSidebarWidth={260}
    />
  );
}
