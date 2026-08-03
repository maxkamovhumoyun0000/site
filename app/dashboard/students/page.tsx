import { ClientRedirect } from "../../ui/client-redirect";

export default function DashboardStudentsPage() {
  return <ClientRedirect href="/?role=admin&section=users" />;
}
