import type { Metadata } from "next";
import { Geist } from "next/font/google";

import { SiteHeader } from "@/components/SiteHeader";
import { cn } from "@/lib/utils";
import { Providers } from "./providers";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "AI Advisory Platform",
  description: "Assess organizational readiness for AI adoption — deterministic findings, AI-explained.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("font-sans", geist.variable)}>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>
          <div className="flex min-h-screen flex-col">
            <SiteHeader />
            <main className="flex-1">{children}</main>
            <footer className="border-t py-6">
              <div className="mx-auto max-w-6xl px-4 text-xs text-muted-foreground sm:px-6">
                AI Advisory Platform — deterministic findings, AI-explained, every recommendation
                traceable and grounded.
              </div>
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
