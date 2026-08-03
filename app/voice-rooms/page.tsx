"use client";

import { useEffect, useState } from "react";
import { StudentVoiceRoom } from "../ui/voice-room/student-voice-room";

export default function VoiceRoomsPage() {
  const [data, setData] = useState<any>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Basic auth check
    const token = localStorage.getItem("diamond_token");
    if (!token) {
      window.location.href = "/auth/login";
      return;
    }
    setData({ role: "student" }); // Mock data for now, StudentVoiceRoom uses useVoiceRoom
    setLoading(false);
  }, []);

  if (loading) {
    return <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col fixed inset-0 overflow-hidden z-[9999]">
      <StudentVoiceRoom data={data} />
    </div>
  );
}
