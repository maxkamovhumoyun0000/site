"use client";

import { useParams, useRouter } from "next/navigation";
import { AiTestRunner } from "@/app/ui/ai-test-runner";

export default function AiTestPage() {
  const params = useParams();
  const router = useRouter();
  const rawType = String(params?.sourceType || "library_test");
  const sourceType =
    rawType === "homework" || rawType === "weekly_review" ? rawType : "library_test";
  const id = Number(params?.sourceId || 0);

  return (
    <div className="min-h-screen bg-surface dark:bg-navy-950">
      <AiTestRunner
        sourceType={sourceType as "library_test" | "homework" | "weekly_review"}
        sourceId={sourceType === "library_test" ? id : undefined}
        homeworkId={sourceType === "homework" || sourceType === "weekly_review" ? (id || undefined) : undefined}
        onExit={() => router.back()}
      />
    </div>
  );
}
