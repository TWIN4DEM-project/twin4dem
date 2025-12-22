import { useSimulations } from "./hooks.ts";
import { SimulationListItem } from "./SimulationListItem";

export function SimulationList() {
  const { data, loading } = useSimulations();
  const simulationListItems = data.map((x) => (
    <SimulationListItem key={x.id} item={x} />
  ));
  return loading ? (
    <div>Loading...</div>
  ) : (
    <ul className="simulationList">{simulationListItems}</ul>
  );
}
