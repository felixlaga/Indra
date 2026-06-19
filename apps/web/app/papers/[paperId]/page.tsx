import type { Metadata } from "next";

import { PaperPageClient } from "@/components/paper-page-client";

export const metadata: Metadata = { title: "Paper" };

export default async function PaperPage({
  params,
}: {
  params: Promise<{ paperId: string }>;
}) {
  const { paperId } = await params;
  return <PaperPageClient paperId={paperId} />;
}
