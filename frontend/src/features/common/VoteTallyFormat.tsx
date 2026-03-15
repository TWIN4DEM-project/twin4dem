import { isMotionSuccessful, type VoteTally } from "@/features/common/utils.ts";

interface VoteTallyFormatProps {
  votes: VoteTally;
}

export function VoteTallyFormat({ votes }: VoteTallyFormatProps) {
  const motionSuccessful = isMotionSuccessful(votes);

  return (
    <p>
      With{" "}
      <b>
        {votes.for} votes <em>for</em>
      </b>
      ,{" "}
      <b>
        {votes.against} votes <em>against</em>
      </b>
      , and{" "}
      <b>
        {votes.abstain} <em>abstentions</em>
      </b>
      , the motion {motionSuccessful ? "passes" : "fails"}.
    </p>
  );
}
