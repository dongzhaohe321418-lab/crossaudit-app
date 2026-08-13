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

/* Scroll reveal runs from here, not from a React effect, so a slow or failed
   hydration can never leave a section blank. It marks the document (html.js)
   so the CSS only hides a section once this script is present to reveal it,
   then reveals with an IntersectionObserver plus scroll and load fallbacks;
   reduced-motion or a missing observer shows everything at once. */
const REVEAL_SCRIPT = `(function(){
  var root=document.documentElement;root.classList.add('js');
  function all(){return [].slice.call(document.querySelectorAll('[data-reveal]'));}
  function show(el){el.classList.add('is-visible');}
  function sweep(){all().forEach(function(el){if(el.classList.contains('is-visible'))return;var r=el.getBoundingClientRect();if(r.top<window.innerHeight*0.94&&r.bottom>0)show(el);});}
  function arm(){
    var els=all();if(!els.length){window.setTimeout(arm,60);return;}
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches||!('IntersectionObserver' in window)){els.forEach(show);return;}
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){show(e.target);io.unobserve(e.target);}});},{rootMargin:'0px 0px -8%',threshold:0.12});
    els.forEach(function(el){io.observe(el);});
    sweep();
    window.addEventListener('scroll',sweep,{passive:true});
    window.addEventListener('load',function(){window.setTimeout(sweep,300);});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',arm);else arm();
})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${dmSans.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: REVEAL_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
