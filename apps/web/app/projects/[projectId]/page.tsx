import type { Metadata } from "next";

import { ProjectPageClient } from "@/components/project-page-client";

export const metadata: Metadata = { title: "Project" };

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ProjectPageClient projectId={projectId} />;
}
