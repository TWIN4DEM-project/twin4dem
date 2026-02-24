import {useEffect, useMemo, useState, useRef, useCallback} from "react";
import {useParams} from "react-router";
import {fetchSettings, useSimulation} from "@/features/simulations/hooks.ts";
import {z} from "zod";
import {useWebSocketStream} from "@/hooks/websocket.ts";
import {type SimulationState, SimulationStateSchema, StepResultSchema} from "@/types/state.ts";
import {type UserSettings} from "@/types/settings.ts";
import {SubmodelContainer} from "@/features/simulations/SubmodelContainer.tsx";
import type {AgentVote} from "@/features/common/utils.ts";
import {
  type Judge,
  type MemberOfParliament,
  type Minister,
  type Simulation, type SimulationParam
} from "@/types/simulation.ts";
import './SimulationDetails.scss';

const SimulationIdParamSchema = z.coerce.number().int().positive();

type StepResult = z.infer<typeof StepResultSchema>;

export interface Votes {
  cabinet: AgentVote<Minister>[];
  parliament: AgentVote<MemberOfParliament>[];
  court: AgentVote<Judge>[];
}


function accessor<T>(x: SimulationParam): T[]  {
  switch(x.type) {
    case "cabinet":
      return x.cabinet.ministers as T[];
    case "parliament":
      return x.parliament.members as T[];
    case "court":
      return x.court.judges as T[];
  }
}

function getBranchMembers<T>(
    data: Simulation | undefined,
    predicate: (x: SimulationParam) => boolean): T[] {
  const dataPoints = data?.params.filter(predicate);
  return (!dataPoints?.length)
      ? [] : accessor(dataPoints[0]);
}

function getInitialBranchVotes<T>(branchMembers: T[]): AgentVote<T>[] {
  return branchMembers.map(bm => ({
        agent: bm,
        vote: null,
      })
  )
}

function getUpdatedVotes<T extends {id: number}>(
    results: StepResult[],
    predicate: (x: StepResult) => boolean,
    currentVotes: AgentVote<T>[]
): AgentVote<T>[] | undefined {
  const branchResults = results.filter(predicate);
  if (branchResults.length == 0) return undefined;

  const result = branchResults[0];
  return currentVotes.map((v) => {
    const memberId = v.agent.id;
    const raw = result.votes?.[memberId] ?? null; // 0 | 1 | null
    const vote = raw === 1 ? true : raw === 0 ? false : null; // boolean | null
    return {...v, vote};
  });
}

type SimulationDetailsParams = {
  updateSimulationStep: (simulationId: number, newStep: number) => void;
}

export function SimulationDetails({updateSimulationStep}: SimulationDetailsParams) {
  const { simulationId } = useParams();
  const [path, setPath] = useState<"legislative act" | "decree" | undefined>();
  const [aggrandizementPassed, setAggrandizementPassed] = useState<
    boolean | null
  >(null);
  const [stepNo, setStepNo] = useState<number>(0);
  const [settings, setSettings] = useState<UserSettings|null>(null);
  const loadSettings = useCallback(async () => {
      const userSettings = await fetchSettings()
      setSettings(userSettings)
    }, [])
  const parsed = SimulationIdParamSchema.safeParse(simulationId);
  const simulationIdNo = parsed.success ? parsed.data : undefined;
  const { data } = useSimulation(simulationIdNo);
  const [votes, setVotes] = useState<Votes>({ cabinet: [], parliament: [], court: [] });
  const votesRef = useRef(votes);

  useEffect(() => {
    votesRef.current = votes;
  }, [votes]);

  const { send, stream } = useWebSocketStream<SimulationState>(
    `ws://localhost:8000/ws/simulation/${simulationId}/`,
  );
  const parties = useMemo<string[]>(() => {
      if (settings === null) return [];

      return settings.parties.map(
          (p) => `${p.label}(${p.position})`
      ).sort()
  }, [settings]);

  useEffect(() => {loadSettings().catch(console.error)}, [loadSettings])

  useEffect(() => {
    setStepNo(data?.currentStep || 0);
  }, [data]);

  useEffect(() => {
    const voteState = {
      cabinet: getInitialBranchVotes(
          getBranchMembers<Minister>(data, x => x.type === "cabinet")
      ),
      parliament: getInitialBranchVotes(
          getBranchMembers<MemberOfParliament>(data, x => x.type === "parliament")
      ),
      court: getInitialBranchVotes(
          getBranchMembers<Judge>(data, x => x.type === "court")
      ),
    }

    setVotes(voteState);
  }, [data]);


  useEffect(() => {
    (async () => {
      for await (const msg of stream) {
        const res = await SimulationStateSchema.safeParseAsync(msg);
        if (!res.success) continue;

        setStepNo(res.data.stepNo);
        let votes = { ...votesRef.current };

        const results = res.data.results;

        const cabinetResults = results.filter((r)=> r.type=="cabinet")
        if (cabinetResults.length > 0) {
          setPath(cabinetResults[0].path);
          updateSimulationStep(simulationIdNo!, res.data.stepNo);
        } else {
          break;
        }

        const cabinetUpdate = getUpdatedVotes<Minister>(
            results,
            x => x.type === "cabinet",
            votes.cabinet
        );
        if (cabinetUpdate !== undefined) {
          votes.cabinet = cabinetUpdate;
        }

        const parliamentUpdate = getUpdatedVotes(
            results,
            x => x.type === "parliament",
            votes.parliament
        );
        if (parliamentUpdate !== undefined) {
          votes.parliament = parliamentUpdate;
        }

        const courtUpdate = getUpdatedVotes(
            results,
            x => x.type === "court",
            votes.court
        );
        if (courtUpdate !== undefined) {
          votes.court = courtUpdate;
        }

        setVotes(votes);
        setAggrandizementPassed(
          res.data.results
            .map((result) => result.approved)
            .reduce((prev, current) => prev && current),
        );
      }
    })()
  }, [stream, votes]);

  return (
    <div className="simulationDetails">
      <div className="simulationToolbar simulationDetailsToolbar">
        <h3 className="simulationDetailsTitle">Simulation {simulationId}</h3>
        <button
          className="button button--outline"
          onClick={() => send({ action: "step" })}
          aria-label={`Step ${stepNo + 1}`}
          title={`Step ${stepNo + 1}`}
        >
          &#x23ED;{` ${stepNo + 1}`}
        </button>
      </div>

      <div className="simulationHeader">
        <div className="executiveContainer">
          <h4>Executive Sub-model - {votes.cabinet?.label || "unknown"}</h4>
          <div className="executiveContainerHeader">
            <p>
              The cabinet was configured with an overall probability of&nbsp;
              <b>{votes.cabinet?.governmentProbabilityFor}</b> to vote
              pro-aggrandisement. After the vote, the probability that the
              aggrandisement unit will be sent to the parliament for approval is{" "}
              <b>{votes.cabinet?.legislativeProbability}</b>.
            </p>
          </div>
        </div>
      </div>
        <SubmodelContainer parties={parties} votes={votes} path={path as "legislative act" | "decree" | undefined}
                           step={stepNo} aggrandizementPassed={aggrandizementPassed}/>
    </div>
  );
}
