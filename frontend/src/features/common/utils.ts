import type {MinisterVote} from "@/features/executive/MinisterNetwork.tsx";
import type {MemberVote} from "@/features/legislative/ParliamentBeeswarm.tsx";
import type {JudgeVote} from "@/features/court/CourtBeeswarm.tsx";

export interface VoteTally {
    "for": number,
    "against": number,
    "abstain": number
}

export function tallyVotes(branchVotes: MinisterVote[] | MemberVote[] | JudgeVote[]): VoteTally {
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