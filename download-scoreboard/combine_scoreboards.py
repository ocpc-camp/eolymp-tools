import sys

from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class Problem:
    id: str
    long_name: str
    penalty_time: int
    unknown: int


@dataclass
class Team:
    id: int
    name: str
    unknown1: int
    unknown2: int


@dataclass
class Submission:
    team_id: int
    problem_id: str
    attempt_no: int
    time: int
    verdict: str


@dataclass
class Contest:
    name: str
    length: int
    problems: list[Problem] = field(default_factory=list)
    teams: list[Team] = field(default_factory=list)
    submissions: list[Submission] = field(default_factory=list)


def merge_contests(contest1: Contest, contest2: Contest) -> Contest:
    result = Contest(name=contest1.name, length=contest1.length, problems=contest1.problems.copy())

    first_free_team_id = 1 + max(team.id for team in contest1.teams)
    contest2_id_to_merged_id = {}
    for team in contest2.teams:
        contest2_id_to_merged_id[team.id] = first_free_team_id
        first_free_team_id += 1

    result.teams.extend(contest1.teams)
    for team in contest2.teams:
        result.teams.append(Team(contest2_id_to_merged_id[team.id], team.name, team.unknown1, team.unknown2))

    result.submissions.extend(contest1.submissions)
    for sub in contest2.submissions:
        result.submissions.append(Submission(contest2_id_to_merged_id[sub.team_id], sub.problem_id, sub.attempt_no, sub.time, sub.verdict))

    result.submissions.sort(key=lambda sub: sub.time)

    return result


def write_contest(contest: Contest, out: TextIO):
    out.write(f"@contest {contest.name}\n")
    out.write(f"@contlen {contest.length}\n")
    out.write(f"@problems {len(contest.problems)}\n")
    out.write(f"@teams {len(contest.teams)}\n")
    out.write(f"@submissions {len(contest.submissions)}\n")

    for problem in contest.problems:
        out.write(f"@p {problem.id},{problem.long_name},{problem.penalty_time},{problem.unknown}\n")
    for team in contest.teams:
        out.write(f"@t {team.id},{team.unknown1},{team.unknown2},{team.name}\n")
    for submission in contest.submissions:
        out.write(f"@s {submission.team_id},{submission.problem_id},{submission.attempt_no},{submission.time},{submission.verdict}\n")


def read_contest(file: TextIO) -> Contest:
    result = Contest(name="name not set", length=0)
    for line in file:
        tokens = line.strip().split(" ", 1)
        if tokens[0] == "@contest":
            result.name = tokens[1]
        elif tokens[0] == "@contlen":
            result.length = int(tokens[1])
        elif tokens[0] == "@problems":
            pass
        elif tokens[0] == "@teams":
            pass
        elif tokens[0] == "@submissions":
            pass
        elif tokens[0] == "@p":
            params = tokens[1].split(",")
            if len(params) != 4:
                print(f"unexpected number of parameters in @p directive: {tokens[1]}", file=sys.stderr)
            else:
                result.problems.append(Problem(params[0], params[1], int(params[2]), int(params[3])))
        elif tokens[0] == "@t":
            params = tokens[1].split(",", 3)
            if len(params) != 4:
                print(f"unexpected number of parameters ({len(params)}) in @t directive: {tokens[1]}", file=sys.stderr)
            else:
                result.teams.append(Team(int(params[0]), params[3], int(params[1]), int(params[2])))
        elif tokens[0] == "@s":
            params = tokens[1].split(",")
            if len(params) != 5:
                print(f"unexpected number of parameters in @s directive: {tokens[1]}", file=sys.stderr)
            else:
                result.submissions.append(Submission(int(params[0]), params[1], int(params[2]), int(params[3]), params[4]))
        else:
            print(f"unexpected directive: {tokens[0]}")

    return result


if __name__ == "__main__":
    with open(sys.argv[1]) as f1:
        contest1 = read_contest(f1)
    with open(sys.argv[2]) as f2:
        contest2 = read_contest(f2)

    merged = merge_contests(contest1, contest2)

    write_contest(merged, sys.stdout)