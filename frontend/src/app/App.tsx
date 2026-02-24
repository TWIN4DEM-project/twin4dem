import { BrowserRouter, Route, Routes } from "react-router";
import "@scss/base.scss";
import "./App.scss";

import { SidePaneLayout } from "@/layouts/two-pane/SidePaneLayout.tsx";
import { SimulationList } from "@/features/simulations/SimulationList";
import { SimulationDetails } from "@/features/simulations/SimulationDetails";
import { EmptySelectionPane } from "@/components/EmptySelectionPane";
import { useSimulations } from "@/features/simulations/hooks";

export function App() {
  const { data, setData, loading, refetch } = useSimulations();
  function updateSimulationStep(simulationId: number, newStep: number) {

    setData( data =>
      data?.map((simulation) =>
        simulation.id === simulationId
          ? { ...simulation, currentStep: newStep }
          : simulation,
      ),
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <SidePaneLayout
              side={
                <SimulationList
                  data={data}
                  loading={loading}
                  refetch={refetch}
                />
              }
            />
          }
        >
          <Route
            index
            element={
              <EmptySelectionPane text="Please select a simulation &#129760;" />
            }
          />
          <Route
            path="simulations/:simulationId"
            element={
              <SimulationDetails updateSimulationStep={updateSimulationStep} />
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
