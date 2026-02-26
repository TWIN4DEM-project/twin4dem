import { BrowserRouter, Route, Routes } from "react-router";
import "@scss/base.scss";

import { SidePaneLayout } from "@/layouts/two-pane/SidePaneLayout.tsx";
import { SimulationList } from "@/features/simulations/SimulationList";
import { SimulationDetails } from "@/features/simulations/SimulationDetails";
import { EmptySelectionPane } from "@/components/EmptySelectionPane";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<SidePaneLayout side={<SimulationList />} />}>
          <Route
            index
            element={
              <EmptySelectionPane text="Please select a simulation &#129760;" />
            }
          />
          <Route
            path="simulations/:simulationId"
            element={<SimulationDetails />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
