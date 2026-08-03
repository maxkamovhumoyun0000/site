import { ClientRedirect } from "../../ui/client-redirect";

export default function TeacherAttendancePage() {
  return <ClientRedirect href="/?role=teacher&section=attendance" />;
}
