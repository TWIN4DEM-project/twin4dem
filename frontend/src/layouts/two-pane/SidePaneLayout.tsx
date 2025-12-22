import * as React from "react";
import { Outlet } from "react-router";
import "./SidePaneLayout.scss";

type SidePaneLayoutProps = {
  side: React.ReactNode;
};

export function SidePaneLayout({ side }: SidePaneLayoutProps) {
  return (
    <div className="sidePaneLayout">
      <aside className="sidePane">{side}</aside>
      <main className="contentPane">
        <Outlet />
      </main>
    </div>
  );
}
