import { StudentCompetitionRedirect } from "../../competition-redirect";

export default function StudentDuelOneVsOnePage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  return <StudentCompetitionRedirect section="duel-1v1" arenaMode="duel-1v1" searchParams={searchParams} />;
}
