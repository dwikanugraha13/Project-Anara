import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Anara - AI 3D Suara & Teks",
  description:
    "Anara - AI interaktif dengan avatar 3D real-time, sinkronisasi gerak bibir, dan percakapan suara alami.",
  keywords: ["Anara", "asisten suara", "avatar 3D", "lip sync", "Gemini Live"],
  authors: [{ name: "Anara Project" }],
  other: {
    google: "notranslate",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="id"
      className={inter.variable}
      suppressHydrationWarning
      style={{ backgroundColor: "#030712" }}
    >
      <head>
        <meta name="google" content="notranslate" />
      </head>
      <body
        className="antialiased text-white notranslate"
        translate="no"
        suppressHydrationWarning
        style={{ backgroundColor: "#030712", margin: 0, padding: 0 }}
      >
        {children}
      </body>
    </html>
  );
}
