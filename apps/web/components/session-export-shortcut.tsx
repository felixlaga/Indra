"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SessionExportShortcut() {
  const pathname = usePathname();
  const match = pathname.match(/^\/sessions\/([^/]+)$/);
  if (!match) return null;
  return (
    <Link className="session-export-shortcut" href={`/sessions/${match[1]}/exports`}>
      Export artifacts
    </Link>
  );
}
