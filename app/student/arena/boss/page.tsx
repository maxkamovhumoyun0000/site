import { StudentCompetitionRedirect } from "../../competition-redirect";

export default function StudentBossArenaPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  return <StudentCompetitionRedirect section="arena-boss" arenaMode="arena-boss" searchParams={searchParams} />;
}
