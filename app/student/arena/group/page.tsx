import { redirect } from "next/navigation";

export default function StudentGroupArenaPage() {
  redirect("/?role=student&section=arena");
}
