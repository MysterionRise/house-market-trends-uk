import type { Metadata, Viewport } from "next";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "UK Liveability Index",
  description: "Explore the UK's neighbourhoods with open data and an AI assistant.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Same logic as components/ThemeProvider.tsx, run before the first paint so a saved
// theme never flashes the other one. Keep the two in step.
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("lix.theme"),r=document.documentElement;if(t==="light"||t==="dark")r.dataset.theme=t;else t="system";r.classList.toggle("dark",t==="dark"||(t==="system"&&matchMedia("(prefers-color-scheme: dark)").matches))}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
