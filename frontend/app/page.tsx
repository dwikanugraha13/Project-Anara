import { cookies } from "next/headers";
import HomePageClient from "./HomePageClient";

export default async function Page() {
  const cookieStore = await cookies();
  const rawWidth = cookieStore.get("anara_sidebar_width")?.value;
  const parsedWidth = rawWidth ? parseInt(rawWidth, 10) : 380;
  const initialSidebarWidth = !isNaN(parsedWidth) && parsedWidth >= 380 && parsedWidth <= 1050 ? parsedWidth : 380;

  return (
    <HomePageClient
      initialSidebarTab="history"
      initialSidebarWidth={initialSidebarWidth}
    />
  );
}
