"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SessionMapShortcut() {
  const pathname = usePathname();
  const match = pathname.match(/^\/sessions\/([^/]+)$/);
  if (!match) return null;
  const sessionId = match[1];
  return (
    <div className="session-shortcuts">
      <Link className="session-map-shortcut" href={`/sessions/${sessionId}/map`}>
        Research map
      </Link>
      <Link className="session-map-shortcut" href={`/sessions/${sessionId}/advisor`}>
        Research advisor
      </Link>
    </div>
  );
}
