import type { Metadata } from "next";

import { SessionExportShortcut } from "@/components/session-export-shortcut";
import { SessionMapShortcut } from "@/components/session-map-shortcut";

import "./globals.css";
import "./phase5.css";

export const metadata: Metadata = {
  title: {
    default: "Indra Research Navigator",
    template: "%s · Indra",
  },
  description: "Evidence-backed research navigation and session mission control.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {children}
        <SessionMapShortcut />
        <SessionExportShortcut />
      </body>
    </html>
  );
}
