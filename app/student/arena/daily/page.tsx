import { redirect } from "next/navigation";

export default function StudentDailyArenaPage() {
  redirect("/?role=student&section=arena");
}
