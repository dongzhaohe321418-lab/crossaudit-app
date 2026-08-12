import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

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
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
