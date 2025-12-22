import { type SimulationListItem } from "@/types/simulation.ts";
import { Link } from "react-router";
import "./SimulationList.scss";
import dayjs from "dayjs";

interface SimulationListItemProps {
  item: SimulationListItem;
}

export function SimulationListItem({ item }: SimulationListItemProps) {
  return (
    <li>
      <Link to={`simulations/${item.id}`}>
        <b>{item.status}</b> @ step {item.currentStep} <br />[
        <i>{dayjs(item.updatedAt).format("YYYY-MM-DD HH:mm")}</i>]
      </Link>
    </li>
  );
}
