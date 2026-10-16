import type { Metadata } from "next";
import localFont from "next/font/local";
import { QueryProvider } from "@/components/providers/query-provider";
import "./globals.css";

// Self-hosted (Latin subset, the files Google Fonts serves) so the build never
// downloads fonts: fetching them from Google intermittently failed CI builds.
// Onest and Plus Jakarta Sans are variable fonts, one file each; Poppins ships
// one file per weight. Licenses sit beside the files. Onest + Poppins match the
// landing page's type.
const onest = localFont({
  variable: "--font-onest",
  src: "./fonts/onest-latin.woff2",
  weight: "100 900",
});

const poppins = localFont({
  variable: "--font-poppins",
  src: [
    { path: "./fonts/poppins-latin-400.woff2", weight: "400" },
    { path: "./fonts/poppins-latin-500.woff2", weight: "500" },
    { path: "./fonts/poppins-latin-600.woff2", weight: "600" },
    { path: "./fonts/poppins-latin-700.woff2", weight: "700" },
    { path: "./fonts/poppins-latin-800.woff2", weight: "800" },
    { path: "./fonts/poppins-latin-900.woff2", weight: "900" },
  ],
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
      className={[onest.variable, poppins.variable, ibmPlexMono.variable, plusJakartaSans.variable].join(" ")}
    >
      <head>
        <link
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"
          rel="stylesheet"
        />
      </head>
      <body
        className="antialiased"
        style={{ fontFamily: "var(--font-poppins)" }}
        suppressHydrationWarning
      >
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
