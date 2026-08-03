import { StudentCompetitionRedirect } from "../../competition-redirect";

export default function StudentDuelThreeVsThreePage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  return <StudentCompetitionRedirect section="duel-3v3" arenaMode="duel-3v3" searchParams={searchParams} />;
}
