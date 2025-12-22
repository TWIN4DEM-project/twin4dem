import "./EmptySelectionPane.scss";

interface EmptySelectionPaneProps {
  text: string;
}

export function EmptySelectionPane({
  text = "No data...",
}: EmptySelectionPaneProps) {
  return (
    <div className="emptySelection">
      <p>{text}</p>
    </div>
  );
}
