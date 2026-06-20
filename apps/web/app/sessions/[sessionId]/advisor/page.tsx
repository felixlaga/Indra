import type { Metadata } from "next";

import { ResearchAdvisorPageClient } from "@/components/research-advisor-page-client";

export const metadata: Metadata = { title: "Research advisor" };

export default async function ResearchAdvisorPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ResearchAdvisorPageClient sessionId={sessionId} />;
}
