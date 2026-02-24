export interface VoteTally {
    "for": number,
    "against": number,
    "abstain": number
}

export interface AgentVote<T> {
    agent: T,
    vote: boolean | null,
}

export function tallyVotes(branchVotes: AgentVote<any>[]): VoteTally {
    return branchVotes.reduce(
        (voteRecord, currentVote) => {
            const vote = currentVote.vote;
            if (vote === null) {
                voteRecord["abstain"] += 1;
            } else if (vote) {
                voteRecord["for"] += 1;
            } else {
                voteRecord["against"] += 1;
            }
            return voteRecord;
        }, {"for": 0, "against": 0, "abstain": 0});
}

export function isMotionSuccessful(votes: VoteTally) {
    return votes["for"] > votes["against"];
}

export function headingSummaryResult(votes: VoteTally, isActive: boolean) {
    if (!isActive) return "";
    return isMotionSuccessful(votes) ? ": Pass" : ": Fail";
}