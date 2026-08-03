import { ClientRedirect } from "../../ui/client-redirect";

export default function StudentDashboardPage() {
  return <ClientRedirect href="/?role=student&section=home" />;
}
