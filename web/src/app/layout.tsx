import type { Metadata } from "next";
import localFont from "next/font/local";
import { QueryProvider } from "@/components/providers/query-provider";
import "./globals.css";

// Self-hosted (Latin subset, the files Google Fonts serves) so the build never
// downloads fonts: fetching them from Google intermittently failed CI builds.
// Fraunces, Public Sans, Lora and Plus Jakarta Sans are variable fonts, one
// file each; licenses sit beside the files.
const fraunces = localFont({
  variable: "--font-fraunces",
  src: "./fonts/fraunces-latin.woff2",
  weight: "400 700",
});

const publicSans = localFont({
  variable: "--font-public-sans",
  src: "./fonts/public-sans-latin.woff2",
  weight: "400 700",
});

const ibmPlexMono = localFont({
  variable: "--font-plex-mono",
  src: [
    { path: "./fonts/ibm-plex-mono-latin-400.woff2", weight: "400" },
    { path: "./fonts/ibm-plex-mono-latin-500.woff2", weight: "500" },
    { path: "./fonts/ibm-plex-mono-latin-600.woff2", weight: "600" },
  ],
});

// The wordmark's face: "bio" at 800, "nocular" at 500.
const plusJakartaSans = localFont({
  variable: "--font-plus-jakarta-sans",
  src: "./fonts/plus-jakarta-sans-latin.woff2",
  weight: "500 800",
});

// Kept: still referenced via --font-lora in dashboard/page.tsx
const lora = localFont({
  variable: "--font-lora",
  src: "./fonts/lora-latin.woff2",
  weight: "400 700",
});

export const metadata: Metadata = {
  title: "Bionocular.ai — Human‑Verified Oncology Signal, Not Noise",
  description: "AI signal detection plus expert verification across trials, publications, pipelines, and real‑world data. Faster oncology insights your teams can trust.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // The font variables go on <html>, not <body>: globals.css aliases them on
    // :root (--font-display, --font-mono), and an alias there can only see
    // variables set on that same element.
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={[fraunces.variable, publicSans.variable, ibmPlexMono.variable, lora.variable, plusJakartaSans.variable].join(" ")}
    >
      <head>
        <link
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"
          rel="stylesheet"
        />
      </head>
      <body
        className="antialiased"
        style={{ fontFamily: "var(--font-public-sans)" }}
        suppressHydrationWarning
      >
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
