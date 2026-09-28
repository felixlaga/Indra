import type { Metadata } from "next";

import "./globals.css";
import "./phase5.css";
import "./session-hub.css";

export const metadata: Metadata = {
  title: {
    default: "Indra Research Navigator",
    template: "%s · Indra",
  },
  description:
    "Evidence-backed research navigation and session mission control.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
