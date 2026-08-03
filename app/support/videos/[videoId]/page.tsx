"use client";

import { RoleVideoDetailPage } from "@/app/ui/role-video-detail";

export default function SupportVideoDetailPage({ params }: { params: { videoId: string } }) {
  return <RoleVideoDetailPage role="support" videoId={params.videoId} />;
}
