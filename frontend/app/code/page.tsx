import { cookies } from "next/headers";
import CodePageClient from "./CodePageClient";

export const metadata = {
  title: "Anara Code Studio — Autonomous AI Coding Agent",
  description: "Independent Workspace IDE, CodeMirror 6, and PowerShell Terminal powered by Autonomous AI Agent.",
};

export default async function CodePage() {
  const cookieStore = await cookies();
  const rawLeft = cookieStore.get("anara_studio_left_width")?.value;
  const parsedLeft = rawLeft ? parseInt(rawLeft, 10) : 260;
  const initialSidebarWidth = !isNaN(parsedLeft) && parsedLeft >= 180 && parsedLeft <= 500 ? parsedLeft : 260;

  const rawRight = cookieStore.get("anara_studio_right_width")?.value;
  const parsedRight = rawRight ? parseInt(rawRight, 10) : 450;
  const initialRightWidth = !isNaN(parsedRight) && parsedRight >= 340 && parsedRight <= 700 ? parsedRight : 450;

  const rawTermH = cookieStore.get("anara_studio_term_height")?.value;
  const parsedTermH = rawTermH ? parseInt(rawTermH, 10) : 210;
  const initialTerminalHeight = !isNaN(parsedTermH) && parsedTermH >= 100 && parsedTermH <= 500 ? parsedTermH : 210;

  const rawTermOpen = cookieStore.get("anara_studio_term_open")?.value;
  const initialTerminalOpen = rawTermOpen !== undefined ? rawTermOpen === "true" : true;

  return (
    <CodePageClient
      initialSidebarWidth={initialSidebarWidth}
      initialRightWidth={initialRightWidth}
      initialTerminalHeight={initialTerminalHeight}
      initialTerminalOpen={initialTerminalOpen}
    />
  );
}
