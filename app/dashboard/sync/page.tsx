import { ClientRedirect } from "../../ui/client-redirect";

export default function DashboardSyncPage() {
  return <ClientRedirect href="/?role=admin&section=home" />;
}
