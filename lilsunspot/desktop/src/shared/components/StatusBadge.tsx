import type { ReactNode } from "react";

type StatusBadgeProps = {
  tone?: "ok" | "warning" | "danger" | "neutral";
  children: ReactNode;
};

export function StatusBadge({ tone = "neutral", children }: StatusBadgeProps) {
  return <span className={`statusBadge ${tone}`}>{children}</span>;
}
