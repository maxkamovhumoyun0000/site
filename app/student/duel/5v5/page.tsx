import { StudentCompetitionRedirect } from "../../competition-redirect";

export default function StudentDuelFiveVsFivePage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  return <StudentCompetitionRedirect section="duel-5v5" arenaMode="duel-5v5" searchParams={searchParams} />;
}
