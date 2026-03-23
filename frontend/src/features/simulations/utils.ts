import type { ReactNode } from "react";
import { createElement, Fragment } from "react";

export function renderNewlines(text: string): ReactNode {
  const lines = text.split("\n");

  return createElement(
    Fragment,
    null,
    ...lines.flatMap((line, index) =>
      index < lines.length - 1 ? [line, createElement("br", { key: index })] : [line],
    ),
  );
}
