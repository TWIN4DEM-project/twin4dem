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
        <b>{item.status}</b> @ step {item.currentStep} <br />[
        <i>{dayjs(item.updatedAt).format("YYYY-MM-DD HH:mm")}</i>]
      </Link>
    </li>
  );
}
