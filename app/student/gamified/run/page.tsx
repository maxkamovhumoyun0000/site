"use client";
import { AiExplanation } from '@/app/ui/ai-explanation';

import { StudentGamified, StudentStandaloneTestShell } from "../../test-views";

export default function StudentGamifiedRunPage() {
  return (
    <StudentStandaloneTestShell>
      {({ data, onNavigate }) => <StudentGamified data={data} onNavigate={onNavigate} />}
    </StudentStandaloneTestShell>
  );
}
