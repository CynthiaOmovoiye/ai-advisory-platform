import type { Metadata } from "next";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Advisory Platform",
  description: "Assess organizational readiness for AI adoption.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <Providers>
          <header className="border-b bg-white">
            <div className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
              <a href="/" className="text-lg font-semibold">AI Advisory Platform</a>
              <nav className="flex gap-4 text-sm text-slate-600">
                <a href="/assessments" className="hover:text-slate-900">Assessments</a>
                <a href="/members" className="hover:text-slate-900">Members</a>
                <a href="/admin" className="hover:text-slate-900">Admin</a>
                <a href="/eval" className="hover:text-slate-900">Evaluation</a>
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
