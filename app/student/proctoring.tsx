"use client";

import { useEffect, type SetStateAction } from "react";

/** Compatibility shape for older screens; biometric checks are retired. */
type ProctoringStatus = {
  user_id: number;
  proctoring_required: boolean;
  face_enrollment_required: boolean;
  face_profile_status: string;
  face_profile_version: number;
  proctoring_block_reason: string | null;
  proctoring_hold_until: string | null;
};

type TestMonitorProps = {
  active?: boolean;
  completed?: boolean;
  initialSessionId?: number | null;
  testType?: string;
  testAttemptRef?: string | null;
  testRoute?: string | null;
  onSessionReady?: (sessionId: number) => void;
  onVerificationStateChange?: (ready: boolean, reason?: string) => void;
  onTerminated?: (reason: string) => void;
  className?: string;
};

const DISABLED_STATUS: ProctoringStatus = {
  user_id: 0,
  proctoring_required: false,
  face_enrollment_required: false,
  face_profile_status: "disabled",
  face_profile_version: 0,
  proctoring_block_reason: null,
  proctoring_hold_until: null,
};

export function useStudentProctoringStatus(_enabled = true) {
  return {
    status: DISABLED_STATUS,
    loading: false,
    error: "",
    reload: async () => DISABLED_STATUS,
    setStatus: (_next: SetStateAction<ProctoringStatus | null>) => undefined,
  };
}

export function StudentFaceEnrollmentPanel(_props: {
  status: Record<string, unknown> | null;
  onCompleted?: (payload: Record<string, unknown>) => void;
}) {
  return null;
}

/** No camera access or network request: tests are no longer proctored. */
export function StudentTestProctoring({ onVerificationStateChange }: TestMonitorProps) {
  useEffect(() => {
    onVerificationStateChange?.(true);
  }, [onVerificationStateChange]);
  return null;
}
