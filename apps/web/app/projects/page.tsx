import type { Metadata } from "next";

import { ProjectsPageClient } from "@/components/projects-page-client";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return <ProjectsPageClient />;
}
