"use client";

import React, { use } from "react";
import { StudentSurveyScreen } from "../../ui/student-survey";

export default function SurveyPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);

  return (
    <div className="app-shell min-h-screen">
      <StudentSurveyScreen
        user={null}
        surveyId={resolvedParams.id}
        onFinish={() => {
          window.location.href = "/";
        }}
      />
    </div>
  );
}
