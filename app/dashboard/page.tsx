import { ClientRedirect } from "../ui/client-redirect";

export default function DashboardPage() {
  return <ClientRedirect href="/?role=admin&section=home" />;
}
