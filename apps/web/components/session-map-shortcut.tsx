"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SessionMapShortcut() {
  const pathname = usePathname();
  const match = pathname.match(/^\/sessions\/([^/]+)$/);
  if (!match) return null;
  return (
    <Link className="session-map-shortcut" href={`/sessions/${match[1]}/map`}>
      Open research map
    </Link>
  );
}
