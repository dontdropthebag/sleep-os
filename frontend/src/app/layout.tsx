import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sleep Intelligence OS",
  description: "Local-first personal sleep analytics and coaching",
};

const nav = [
  ["/", "Today"],
  ["/nights", "Nights"],
  ["/weekly", "Weekly"],
  ["/trends", "Trends"],
  ["/chronotype", "Chronotype"],
  ["/hrv", "HRV & Recovery"],
  ["/snoring", "Snoring"],
  ["/habits", "Habits"],
  ["/checkin", "Check-in"],
  ["/import", "Import"],
  ["/settings", "Settings"],
  ["/privacy", "Privacy"],
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <div className="mx-auto flex max-w-6xl gap-6 px-4 py-6">
          <aside className="w-44 shrink-0">
            <h1 className="mb-4 text-lg font-bold text-slate-100">
              Sleep<span className="text-sky-400">OS</span>
            </h1>
            <nav aria-label="Main navigation" className="flex flex-col gap-1">
              {nav.map(([href, label]) => (
                <Link
                  key={href}
                  href={href}
                  className="rounded-md px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800 hover:text-white"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
