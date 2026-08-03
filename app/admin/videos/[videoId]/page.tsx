"use client";

import { RoleVideoDetailPage } from "@/app/ui/role-video-detail";

export default function AdminVideoDetailPage({ params }: { params: { videoId: string } }) {
  return <RoleVideoDetailPage role="admin" videoId={params.videoId} />;
}
