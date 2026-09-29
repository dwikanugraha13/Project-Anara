import { cookies } from "next/headers";
import HomePageClient from "./HomePageClient";

export default async function Page() {
  const cookieStore = await cookies();
  const rawWidth = cookieStore.get("anara_sidebar_width")?.value;
  const parsedWidth = rawWidth ? parseInt(rawWidth, 10) : 260;
  const initialSidebarWidth = !isNaN(parsedWidth) && parsedWidth >= 200 && parsedWidth <= 600 ? parsedWidth : 260;

  return (
    <HomePageClient
      initialSidebarTab="history"
      initialSidebarWidth={initialSidebarWidth}
    />
  );
}
