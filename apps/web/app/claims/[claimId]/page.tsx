import type { Metadata } from "next";

import { ClaimPageClient } from "@/components/claim-page-client";

export const metadata: Metadata = { title: "Claim evidence" };

export default async function ClaimPage({
  params,
}: {
  params: Promise<{ claimId: string }>;
}) {
  const { claimId } = await params;
  return <ClaimPageClient claimId={claimId} />;
}
