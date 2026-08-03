"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function ClientRedirect({ href, label = "Yuklanmoqda..." }: { href: string; label?: string }) {
  const router = useRouter();

  useEffect(() => {
    router.replace(href);
  }, [href, router]);

  return (
    <main className="placement-page process-runtime-page">
      <section className="placement-card placement-runtime-card">
        <div className="panel-card text-center text-sm font-black text-navy-900 dark:text-white">
          {label}
        </div>
      </section>
    </main>
  );
}
