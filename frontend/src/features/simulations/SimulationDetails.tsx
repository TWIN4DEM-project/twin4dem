import {useEffect, useMemo, useState, useRef, useCallback} from "react";
import { useParams } from "react-router";
import {fetchSettings, useSimulation} from "@/features/simulations/hooks.ts";
import { z } from "zod";
import { type MinisterVote } from "@/features/executive/MinisterNetwork.tsx";
import { useWebSocketStream } from "@/hooks/websocket.ts";
import { type SimulationState, SimulationStateSchema } from "@/types/state.ts";
import {type UserSettings} from "@/types/settings.ts";
import { type MemberVote } from "@/features/legislative/ParliamentBeeswarm.tsx";
import { type JudgeVote } from "@/features/court/CourtBeeswarm.tsx";
import { SubmodelContainer } from "@/features/simulations/SubmodelContainer.tsx";

import "./SimulationDetails.scss";

const SimulationIdParamSchema = z.coerce.number().int().positive();

type SimulationDetailsState = {
  stepNo: number,
  ministerVotes: MinisterVote[],
  mpVotes: MemberVote[],
  courtVotes: JudgeVote[],
  path: "legislative act" | "decree" | undefined,
  aggrandisementPassed: boolean | null
};

type SimulationDetailsStatePartialType = Partial<SimulationDetailsState>;

type SimulationDetailsParams = {
  updateSimulationStep: (simulationId: number, newStep: number) => void;
}

export function SimulationDetails({updateSimulationStep}: SimulationDetailsParams) {
  // parameters
  const { simulationId } = useParams();

  // load data 
  const parsed = SimulationIdParamSchema.safeParse(simulationId);
  const simulationIdNo = parsed.success ? parsed.data : undefined;
  const { data } = useSimulation(simulationIdNo, true);

  // refs for background state
  const cabinet = useRef(data?.params.find((p) => p.type == "cabinet")?.cabinet);
  const ministers = useRef(cabinet.current?.ministers ?? []);
  const parliament = useRef(data?.params.find((p) => p.type === "parliament")?.parliament);
  const membersOfParliament = useRef(parliament.current?.members ?? []);
  const court = useRef(data?.params.find((p) => p.type === "court")?.court);
  const judges = useRef(court.current?.judges ?? []);

  // refs for websocket handling
  const queueRef = useRef<SimulationState[]>([]);
  const processingRef = useRef(false);

  // settings state
  const [settings, setSettings] = useState<UserSettings|null>(null);

  // parties
  const parties = useMemo<string[]>(() => {
    if (settings === null) return [];

    return settings.parties.map(
        (p) => `${p.label}(${p.position})`
    ).sort()
  }, [settings]);

  // simulation state
  const [simulationState, setSimulationState] = useState<SimulationDetailsState>({
    stepNo: 0,
    ministerVotes: [],
    mpVotes: [],
    courtVotes: [],
    path: undefined,
    aggrandisementPassed: null
  });
  const {stepNo, path, ministerVotes, mpVotes, courtVotes, aggrandisementPassed} = simulationState;

  // websocket
  const { send, stream } = useWebSocketStream<SimulationState>(
    `ws://localhost:8000/ws/simulation/${simulationId}/`,
  );

  // load the settings
  const loadSettings = useCallback(async () => {
    const userSettings = await fetchSettings()
    setSettings(userSettings)
  }, [])

  useEffect(() => {loadSettings().catch(console.error)}, [loadSettings])

  // initial data loading
  useEffect(() => {
    // cabinet and ministers
    cabinet.current = data?.params.find((p) => p.type == "cabinet")?.cabinet;
    ministers.current = cabinet.current?.ministers ?? [];

    // parliament and members
    parliament.current = data?.params.find((p) => p.type === "parliament")?.parliament;
    membersOfParliament.current = parliament.current?.members ?? [];

    // court and judges
    court.current = data?.params.find((p) => p.type === "court")?.court;
    judges.current = court.current?.judges ?? [];

    // set simulation data
    if(data && simulationIdNo) {
      const  myData = {
        stepNo: data.currentStep,
        simulationId: simulationIdNo,
        results: data.results || [],
      } as SimulationState;

      // fill empty result types with default values
      const resultTypes = data.results?.map((result) => result.type) || [];
      const defaultResults = [
        {
          type: "cabinet",
          approved: false,
          path: undefined,
          votes: {},
        },
        {
          type: "parliament",
          approved: false,
          vbar: 0,
          votes: {},
        },
        {
          type: "court",
          approved: false,
          vbar: 0,
          votes: {},
        },
      ] as const;

      defaultResults.forEach((result) => {
        if (!resultTypes.includes(result.type)) {
          myData.results.push(result);
        }
      });

      handleSimulationStep(myData);
    }
  }, [data]);

  // handle one simulation step
  const handleSimulationStep = (data: SimulationState) => {
    const newSimulationState: SimulationDetailsStatePartialType = {};

    // calculate cabinet data
    const cabinet = data.results.find(
      (r) => r.type === "cabinet",
    );

    if (cabinet) {
      const ministerVotes = ministers.current.map((m) => {
        const raw = cabinet.votes?.[m.id] ?? null; // 0 | 1 | null
        const vote = raw === 1 ? true : raw === 0 ? false : null; // boolean | null
        return { minister: m, vote };
      });

      newSimulationState.ministerVotes = ministerVotes;
      newSimulationState.path = cabinet.path;
      newSimulationState.stepNo = data.stepNo;
    }

    // calculate parliament data
    const parliament = data.results.find(
      (r) => r.type === "parliament",
    );

    if (parliament) {
      const mpVotes = membersOfParliament.current.map((m) => {
        const raw = parliament.votes?.[m.id] ?? null; // 0 | 1 | null
        const vote = raw === 1 ? true : raw === 0 ? false : null; // boolean | null
        return { mp: m, vote };
      });

      newSimulationState.mpVotes = mpVotes;
    }

    // calculate court data
    const court = data.results.find((r) => r.type === "court");

    if (court) {
      const courtVotes = judges.current.map((j) => {
        const raw = court.votes?.[j.id] ?? null; // 0 | 1 | null
        const vote = raw === 1 ? true : raw === 0 ? false : null; // boolean | null
        return { judge: j, vote };
      });
      
      newSimulationState.courtVotes = courtVotes
    }

    // find aggrendisement state
    newSimulationState.aggrandisementPassed = data.results.reduce(
      (prev, current) => prev && (current.approved ?? false), true
    );

    setSimulationState((prevSimulationState) => {
      const toRet = ({...prevSimulationState, ...newSimulationState})
      return toRet;
    });

    // if the step number changed, update 
    if(newSimulationState.stepNo && newSimulationState.stepNo !== simulationState.stepNo) {
      updateSimulationStep(simulationIdNo, newSimulationState.stepNo);
    }

  }

  // process the async queue
  const processQueue = async () => {
    if (processingRef.current) return;
    processingRef.current = true;

    while (queueRef.current.length > 0) {
      const msg = queueRef.current.shift()!;
      const res = await SimulationStateSchema.safeParseAsync(msg);

      if (!res.success) continue;

      handleSimulationStep(res.data);
    }

    processingRef.current = false;
  };

  // websocket effect
  useEffect(() => {
    // used to invalidate websocket listening on rerender
    let cancelled = false;

    // listen for messages
    (async () => {
      for await (const msg of stream) {
        if (cancelled) continue;

        queueRef.current.push(msg);
        processQueue();
      }
    })();

    // cancel websocket listening on re-render
    return () => {
      cancelled = false;
    }
  }, [stream]);

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
          <h4>Executive Sub-model - {cabinet.current?.label || "unknown"}</h4>
          <div className="executiveContainerHeader">
            <p>
              The cabinet was configured with an overall probability of&nbsp;
              <b>{cabinet.current?.governmentProbabilityFor}</b> to vote
              pro-aggrandisement. After the vote, the probability that the
              aggrandisement unit will be sent to the parliament for approval is{" "}
              <b>{cabinet.current?.legislativeProbability}</b>.
            </p>
          </div>
        </div>
      </div>

      <SubmodelContainer
        parties={parties}
        ministerVotes={ministerVotes}
        mpVotes={mpVotes}
        courtVotes={courtVotes}
        aggrandizementPassed={aggrandisementPassed}
        path={path}
        step={stepNo}
      />
    </div>
  );
}
