"use client";

import { RoleBookDetailPage } from "@/app/ui/role-book-detail";

export default function SupportBookDetailPage({ params }: { params: { bookId: string } }) {
  return <RoleBookDetailPage role="support" bookId={params.bookId} />;
}
