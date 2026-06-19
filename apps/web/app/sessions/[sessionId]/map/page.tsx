import type { Metadata } from "next";

import { ResearchMapPageClient } from "@/components/research-map-page-client";

export const metadata: Metadata = { title: "Research map" };

export default async function ResearchMapPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ResearchMapPageClient sessionId={sessionId} />;
}
