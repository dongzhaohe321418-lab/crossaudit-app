import type { Metadata } from "next";
import { DM_Sans, IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

const displayFont = Space_Grotesk({
  variable: "--font-display-latin",
  subsets: ["latin"],
  display: "swap",
});

const bodyFont = DM_Sans({
  variable: "--font-body-latin",
  subsets: ["latin"],
  display: "swap",
});

const monoFont = IBM_Plex_Mono({
  variable: "--font-mono-latin",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://crossaudit-v4.vercel.app"),
  title: "CrossAudit | Build with an agent. Ship with evidence.",
  description:
    "A local-first AI work loop that pairs an autonomous generator with an independent auditor before you trust the result.",
  openGraph: {
    title: "CrossAudit | Build with an agent. Ship with evidence.",
    description:
      "One request. Two independent responsibilities. A result you can inspect and trace.",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "CrossAudit independent AI audit loop" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "CrossAudit | Build with an agent. Ship with evidence.",
    description:
      "A local-first AI work loop with independent audit and durable receipts.",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${displayFont.variable} ${bodyFont.variable} ${monoFont.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
