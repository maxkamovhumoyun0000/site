import { redirect } from "next/navigation";

export default function StudentDailyArenaRunPage() {
  redirect("/?role=student&section=arena");
}
