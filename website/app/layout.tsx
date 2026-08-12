import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { DM_Sans, IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

/* Typography direction B (original identity): Space Grotesk display,
   DM Sans body, IBM Plex Mono data. Directions A (Apple system stack)
   and C (Geist) resolve through the same CSS variable layer; see
   globals.css `html[data-type-variant]`. */
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

/* Applies ?type=a|b|c before first paint so the three typography
   directions can be compared from real renders. Defaults to A. */
const typeVariantScript =
  '(function(){try{var t=new URLSearchParams(location.search).get("type");' +
  'if(t==="a"||t==="b"||t==="c"){document.documentElement.setAttribute("data-type-variant",t);}' +
  "}catch(e){}})();";

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
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${spaceGrotesk.variable} ${dmSans.variable} ${plexMono.variable}`}
    >
      <body>
        <script dangerouslySetInnerHTML={{ __html: typeVariantScript }} />
        {children}
      </body>
    </html>
  );
}
