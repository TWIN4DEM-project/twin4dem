import { createSimulation, useSimulations } from "./hooks.ts";
import { SimulationListItem } from "./SimulationListItem";
import { useNavigate, useParams } from "react-router";
import { useMemo } from "react";
import { EmptySelectionPane } from "@/components/EmptySelectionPane.tsx";
import type { SimulationList } from "@/types/simulation.ts";

type SimulationListProps = {
  data: SimulationList | undefined;
  loading: boolean;
  refetch: () => void;
};
export function SimulationList({
  data,
  loading,
  refetch,
}: SimulationListProps) {
  const { simulationId } = useParams();
  const navigate = useNavigate();
  const simulationListItems = useMemo(() => {
    if (!data)
      return <EmptySelectionPane text="No simulations, create one &#128070;" />;
    return data.map((x) => (
      <SimulationListItem
        key={x.id}
        item={x}
        isActive={x.id === Number(simulationId ?? "")}
      />
    ));
  }, [data, simulationId]);

  async function handleAddSimulation() {
    const simulation = await createSimulation();
    refetch();
    navigate(`/simulations/${simulation.id}`);
  }

  return loading && data?.length == 0 ? (
    <div>Loading...</div>
  ) : (
    <div className="simulationListContainer">
      <div className="simulationToolbar simulationListToolbar">
        <h3 className="simulationDetailsTitle">Simulations</h3>
        <button
          className="button button--outline"
          onClick={handleAddSimulation}
        >
          +
        </button>
      </div>
      <ul className="simulationList">{simulationListItems}</ul>
    </div>
  );
}
