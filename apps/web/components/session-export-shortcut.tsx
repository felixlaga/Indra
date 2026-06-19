"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SessionExportShortcut() {
  const pathname = usePathname();
  const match = pathname.match(/^\/sessions\/([^/]+)$/);
  if (!match) return null;
  return (
    <Link
      className="session-map-shortcut"
      href={`/sessions/${match[1]}/exports`}
      style={{ position: "fixed", right: 18, bottom: 66, zIndex: 31 }}
    >
      Export artifacts
    </Link>
  );
}
