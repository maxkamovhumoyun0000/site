"use client";

import { RoleVideoDetailPage } from "@/app/ui/role-video-detail";

export default function TeacherVideoDetailPage({ params }: { params: { videoId: string } }) {
  return <RoleVideoDetailPage role="teacher" videoId={params.videoId} />;
}
