import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { cookies } from "next/headers";
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
  const parsedWidth = rawWidth ? parseInt(rawWidth, 10) : 380;
  const sidebarWidth = !isNaN(parsedWidth) && parsedWidth >= 380 && parsedWidth <= 1050 ? parsedWidth : 380;

  const rawTree = cookieStore.get("anara_tree_width")?.value;
  const parsedTree = rawTree ? parseInt(rawTree, 10) : 210;
  const treeWidth = !isNaN(parsedTree) && parsedTree >= 140 && parsedTree <= 380 ? parsedTree : 210;

  const rawStudioLeft = cookieStore.get("anara_studio_left_width")?.value;
  const parsedStudioLeft = rawStudioLeft ? parseInt(rawStudioLeft, 10) : 260;
  const studioLeftWidth = !isNaN(parsedStudioLeft) && parsedStudioLeft >= 180 && parsedStudioLeft <= 500 ? parsedStudioLeft : 260;

  const rawStudioRight = cookieStore.get("anara_studio_right_width")?.value;
  const parsedStudioRight = rawStudioRight ? parseInt(rawStudioRight, 10) : 450;
  const studioRightWidth = !isNaN(parsedStudioRight) && parsedStudioRight >= 340 && parsedStudioRight <= 700 ? parsedStudioRight : 450;

  return (
    <html
      lang="id"
      className={`preload ${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
      style={{
        backgroundColor: "#030712",
        ["--sidebar-width" as any]: `${sidebarWidth}px`,
        ["--tree-width" as any]: `${treeWidth}px`,
        ["--studio-left-width" as any]: `${studioLeftWidth}px`,
        ["--studio-right-width" as any]: `${studioRightWidth}px`,
      }}
    >
      <head>
        <meta name="google" content="notranslate" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var w = localStorage.getItem('anara_sidebar_width');
                var p = w ? parseInt(w, 10) : ${sidebarWidth};
                if (!isNaN(p) && p >= 380 && p <= 1050) {
                  document.documentElement.style.setProperty('--sidebar-width', p + 'px');
                  document.cookie = 'anara_sidebar_width=' + p + '; path=/; max-age=31536000; SameSite=Lax';
                }
                var tw = localStorage.getItem('anara_tree_width');
                var tp = tw ? parseInt(tw, 10) : ${treeWidth};
                if (!isNaN(tp) && tp >= 140 && tp <= 380) {
                  document.documentElement.style.setProperty('--tree-width', tp + 'px');
                  document.cookie = 'anara_tree_width=' + tp + '; path=/; max-age=31536000; SameSite=Lax';
                }
                var slw = localStorage.getItem('anara_studio_left_width');
                var slp = slw ? parseInt(slw, 10) : ${studioLeftWidth};
                if (!isNaN(slp) && slp >= 180 && slp <= 500) {
                  document.documentElement.style.setProperty('--studio-left-width', slp + 'px');
                  document.cookie = 'anara_studio_left_width=' + slp + '; path=/; max-age=31536000; SameSite=Lax';
                }
                var srw = localStorage.getItem('anara_studio_right_width');
                var srp = srw ? parseInt(srw, 10) : ${studioRightWidth};
                if (!isNaN(srp) && srp >= 340 && srp <= 700) {
                  document.documentElement.style.setProperty('--studio-right-width', srp + 'px');
                  document.cookie = 'anara_studio_right_width=' + srp + '; path=/; max-age=31536000; SameSite=Lax';
                }
              } catch(e) {}
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
        {children}
      </body>
    </html>
  );
}
