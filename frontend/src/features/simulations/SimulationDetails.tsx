import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { useSimulation } from "@/features/simulations/hooks.ts";
import { z } from "zod";
import dayjs from "dayjs";
import {
  MinisterNetwork,
  type MinisterVote,
} from "@/features/executive/MinisterNetwork.tsx";
import { useWebSocketStream } from "@/hooks/websocket.ts";
import { type SimulationState, SimulationStateSchema } from "@/types/state.ts";

const SimulationIdParamSchema = z.coerce.number().int().positive();

export function SimulationDetails() {
  const { simulationId } = useParams();
  const [path, setPath] = useState<string>("-");
  const [stepNo, setStepNo] = useState<number>(0);
  const parsed = SimulationIdParamSchema.safeParse(simulationId);
  const simulationIdNo = parsed.success ? parsed.data : undefined;
  const { data } = useSimulation(simulationIdNo);
  const cabinet = useMemo(() => {
    const cabinets = data?.params.filter((p) => p.type == "cabinet");
    return cabinets ? cabinets[0].cabinet : undefined;
  }, [data]);
  const ministers = useMemo(() => {
    return cabinet?.ministers ? cabinet.ministers : [];
  }, [cabinet]);
  const [ministerVotes, setMinisterVotes] = useState<MinisterVote[]>([]);
  const { send, stream } = useWebSocketStream<SimulationState>(
    `ws://localhost:8000/ws/simulation/${simulationId}/`,
  );

  useEffect(() => {
    setMinisterVotes(
      ministers.map((m) => ({
        minister: m,
        vote: null,
      })),
    );
  }, [ministers]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      for await (const msg of stream) {
        const stepResult = await SimulationStateSchema.safeParseAsync(msg);
        if (!stepResult.success) continue;
        if (cancelled) break;
        setMinisterVotes(
          ministers.map((m) => {
            const raw = stepResult.data.votes?.[m.id] ?? null; // 0 | 1 | null
            const vote = raw === 1 ? true : raw === 0 ? false : null; // boolean | null
            return { minister: m, vote };
          }),
        );
        setPath(stepResult.data.path);
        setStepNo(stepResult.data.t);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [stream, ministers]);

  return (
    <div className="simulationDetails">
      <div className="simulationHeader">
        <div className="simulationToolbar simulationDetailsToolbar">
          <h3 className="simulationDetailsTitle">Simulation {simulationId}</h3>
          <button
            className="simulationToolbarButton"
            onClick={() => send({ action: "step" })}
            aria-label={`Step ${stepNo + 1}`}
            title={`Step ${stepNo + 1}`}
          >
            &#x23ED;{` ${stepNo + 1}`}
          </button>
        </div>
        <div>
          <h4>Global Parameters</h4>
          <table>
            <thead>
              <tr>
                <td>Created At</td>
                <td>Last Modified</td>
                <td>Office Retention Sensitivity (gamma)</td>
                <td>Social Influence Susceptibility (alpha)</td>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{dayjs(data?.createdAt).format("YYYY-MM-DD HH:mm:ss")}</td>
                <td>{dayjs(data?.createdAt).format("YYYY-MM-DD HH:mm:ss")}</td>
                <td>{data?.officeRetentionSensitivity}</td>
                <td>{data?.socialInfluenceSusceptibility}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div className="submodelContainer">
        <div className="executiveContainer">
          <h4>Executive Sub-model - {cabinet?.label || "unknown"}</h4>
          <div className="executiveContainerHeader">
            <p>
              The cabinet was configured with an overall probability of&nbsp;
              <b>{cabinet?.governmentProbabilityFor}</b> to vote
              pro-aggrandisement. After the vote, the probability that the
              aggrandisement unit will be sent to the parliament for approval is{" "}
              <b>{cabinet?.legislativeProbability}</b>.
            </p>
          </div>
          <MinisterNetwork ministerVotes={ministerVotes} />
          <div>
            <b>Path: </b>
            {path}
          </div>
        </div>
      </div>
    </div>
  );
}
