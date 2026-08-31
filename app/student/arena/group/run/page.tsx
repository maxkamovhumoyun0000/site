import { redirect } from "next/navigation";

export default function StudentGroupArenaRunPage() {
  redirect("/?role=student&section=arena");
}
