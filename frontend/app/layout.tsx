import type { Metadata } from "next";
import Script from "next/script";
import { Inter, JetBrains_Mono } from "next/font/google";
import { cookies } from "next/headers";
import { GatewayAuthModal } from "@/components/gateway/GatewayAuthModal";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Anara - AI 3D Suara & Teks",
  description:
    "Anara - Interactive AI with real-time 3D avatar, lip sync, and natural voice conversation.",
  keywords: ["Anara", "asisten suara", "avatar 3D", "lip sync", "Gemini Live"],
  authors: [{ name: "Anara Project" }],
  other: {
    google: "notranslate",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const rawWidth = cookieStore.get("anara_sidebar_width")?.value;
  const parsedWidth = rawWidth ? parseInt(rawWidth, 10) : 260;
  const sidebarWidth = !isNaN(parsedWidth) && parsedWidth >= 200 && parsedWidth <= 600 ? parsedWidth : 260;

  const rawTree = cookieStore.get("anara_tree_width")?.value;
  const parsedTree = rawTree ? parseInt(rawTree, 10) : 210;
  const treeWidth = !isNaN(parsedTree) && parsedTree >= 140 && parsedTree <= 380 ? parsedTree : 210;

  const rawStudioLeft = cookieStore.get("anara_studio_left_width")?.value;
  const parsedStudioLeft = rawStudioLeft ? parseInt(rawStudioLeft, 10) : 260;
  const studioLeftWidth = !isNaN(parsedStudioLeft) && parsedStudioLeft >= 180 && parsedStudioLeft <= 500 ? parsedStudioLeft : 260;

  const rawStudioRight = cookieStore.get("anara_studio_right_width")?.value;
  const parsedStudioRight = rawStudioRight ? parseInt(rawStudioRight, 10) : 450;
  const studioRightWidth = !isNaN(parsedStudioRight) && parsedStudioRight >= 340 && parsedStudioRight <= 700 ? parsedStudioRight : 450;

  const rootStyle: React.CSSProperties & Record<string, string | number> = {
    backgroundColor: "#030712",
    "--sidebar-width": `${sidebarWidth}px`,
    "--tree-width": `${treeWidth}px`,
    "--studio-left-width": `${studioLeftWidth}px`,
    "--studio-right-width": `${studioRightWidth}px`,
  };

  return (
    <html
      lang="id"
      className={`preload ${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
      style={rootStyle}
    >
      <head>
        <meta name="google" content="notranslate" />
        <Script
          id="anara-layout-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  const setProp = (key, cookieName, fallback, min, max, cssVar) => {
                    const val = localStorage.getItem(key);
                    const parsed = val ? parseInt(val, 10) : fallback;
                    if (!isNaN(parsed) && parsed >= min && parsed <= max) {
                      document.documentElement.style.setProperty(cssVar, parsed + 'px');
                      document.cookie = cookieName + '=' + parsed + '; path=/; max-age=31536000; SameSite=Lax';
                    }
                  };
                  setProp('anara_sidebar_width', 'anara_sidebar_width', ${sidebarWidth}, 200, 600, '--sidebar-width');
                  setProp('anara_tree_width', 'anara_tree_width', ${treeWidth}, 140, 380, '--tree-width');
                  setProp('anara_studio_left_width', 'anara_studio_left_width', ${studioLeftWidth}, 180, 500, '--studio-left-width');
                  setProp('anara_studio_right_width', 'anara_studio_right_width', ${studioRightWidth}, 340, 700, '--studio-right-width');
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body
        className="antialiased text-slate-100 notranslate font-sans"
        translate="no"
        suppressHydrationWarning
        style={{ backgroundColor: "#030712", margin: 0, padding: 0 }}
      >
        <GatewayAuthModal />
        {children}
      </body>
    </html>
  );
}
