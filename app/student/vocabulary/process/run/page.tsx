"use client";

import { StudentStandaloneTestShell, StudentVocabularyProcess } from "../../../test-views";

export default function StudentVocabularyProcessRunPage() {
  return (
    <StudentStandaloneTestShell>
      {({ data, onNavigate }) => <StudentVocabularyProcess data={data} onNavigate={onNavigate} mode="runtime" />}
    </StudentStandaloneTestShell>
  );
}
