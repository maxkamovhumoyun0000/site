"use client";
import { AiExplanation } from '@/app/ui/ai-explanation';

import { StudentStandaloneTestShell, StudentVocabularyProcess } from "../../../test-views";

export default function StudentVocabularyProcessRunPage() {
  return (
    <StudentStandaloneTestShell>
      {({ data, onNavigate }) => <StudentVocabularyProcess data={data} onNavigate={onNavigate} mode="runtime" />}
    </StudentStandaloneTestShell>
  );
}
