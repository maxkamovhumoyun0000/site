"use client";

import { RoleBookDetailPage } from "@/app/ui/role-book-detail";

export default function AdminBookDetailPage({ params }: { params: { bookId: string } }) {
  return <RoleBookDetailPage role="admin" bookId={params.bookId} />;
}
