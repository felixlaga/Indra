import type { Metadata } from "next";

import { ExportCenterPageClient } from "@/components/export-center-page-client";

export const metadata: Metadata = { title: "Research exports" };

export default async function ExportCenterPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ExportCenterPageClient sessionId={sessionId} />;
}
