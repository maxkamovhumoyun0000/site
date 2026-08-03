"use client";

import { RoleBookDetailPage } from "@/app/ui/role-book-detail";

export default function TeacherBookDetailPage({ params }: { params: { bookId: string } }) {
  return <RoleBookDetailPage role="teacher" bookId={params.bookId} />;
}
