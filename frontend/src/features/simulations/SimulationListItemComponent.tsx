import { Link } from "react-router";
import type { SimulationListItem } from "@/types/simulation.ts";
import "./SimulationList.scss";
import dayjs from "dayjs";

interface SimulationListItemProps {
  item: SimulationListItem;
  isActive: boolean;
}

export function SimulationListItemComponent({
  item,
  isActive,
}: SimulationListItemProps) {
  return (
    <li>
      <Link className={isActive ? "active" : ""} to={`simulations/${item.id}`}>
        <b>{item.label}</b> (@ step {item.currentStep}) <br />
        <i>status={item.status}</i> <br />[
        <i>last update: {dayjs(item.updatedAt).format("YYYY-MM-DD HH:mm")}</i>]
      </Link>
    </li>
  );
}
