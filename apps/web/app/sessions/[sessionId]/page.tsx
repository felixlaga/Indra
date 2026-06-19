import type { Metadata } from "next";

import { SessionDashboard } from "@/components/session-dashboard";

export const metadata: Metadata = { title: "Research session" };

export default async function SessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <SessionDashboard sessionId={sessionId} />;
}
