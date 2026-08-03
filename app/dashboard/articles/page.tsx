import { ClientRedirect } from "../../ui/client-redirect";

export default function DashboardArticlesPage() {
  return <ClientRedirect href="/?role=admin&section=articles" />;
}
