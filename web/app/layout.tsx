import type { Metadata, Viewport } from "next";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "UK Liveability Index",
  description: "Explore England's neighbourhoods with open data and an AI assistant.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
