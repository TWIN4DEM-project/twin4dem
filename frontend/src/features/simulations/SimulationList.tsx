import { createSimulation, useSimulations } from "./hooks.ts";
import { SimulationListItem } from "./SimulationListItem";
import { useNavigate } from "react-router";
import { useMemo } from "react";
import { EmptySelectionPane } from "@/components/EmptySelectionPane.tsx";

export function SimulationList() {
  const { data, loading, refetch } = useSimulations();
  const navigate = useNavigate();
  const simulationListItems = useMemo(() => {
    if (!data)
      return <EmptySelectionPane text="No simulations, create one &#128070;" />;
    return data.map((x) => <SimulationListItem key={x.id} item={x} />);
  }, [data]);

  async function handleAddSimulation() {
    const simulation = await createSimulation();
    refetch();
    navigate(`/simulations/${simulation.id}`);
  }

  return loading ? (
    <div>Loading...</div>
  ) : (
    <div className="simulationListContainer">
      <div className="simulationToolbar">
        <button
          className="simulationToolbarButton"
          onClick={handleAddSimulation}
        >
          +
        </button>
      </div>
      <ul className="simulationList">{simulationListItems}</ul>
    </div>
  );
}
