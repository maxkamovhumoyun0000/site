"use client";

import { StudentDailyTestProcess, StudentStandaloneTestShell } from "../../../test-views";

export default function StudentDailyProcessRunPage() {
  return (
    <StudentStandaloneTestShell>
      {({ data, onNavigate }) => <StudentDailyTestProcess data={data} onNavigate={onNavigate} mode="runtime" />}
    </StudentStandaloneTestShell>
  );
}
