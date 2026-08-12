import type { Metadata } from "next";
import { DM_Sans, IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

/* Final typography identity: Space Grotesk carries display and brand,
   DM Sans carries reading text, IBM Plex Mono carries data and evidence. */
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://crossaudit-v4.vercel.app"),
  title: "CrossAudit | Agentic work, independently audited.",
  description:
    "An agentic workspace with cross-vendor supervision: one model does the work, a model from a different provider inspects every committed result before delivery.",
  openGraph: {
    title: "CrossAudit | Agentic work, independently audited.",
    description:
      "One model does the work. A model from a different provider audits every committed result, and every delivery binds to verifiable evidence.",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "CrossAudit independent AI audit loop" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "CrossAudit | Agentic work, independently audited.",
    description:
      "A local-first agentic workspace with cross-vendor independent audit and tamper-evident receipts.",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${dmSans.variable} ${plexMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
