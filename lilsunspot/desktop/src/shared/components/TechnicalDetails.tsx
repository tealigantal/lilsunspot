import type { ReactNode } from "react";

type TechnicalDetailsProps = {
  title?: string;
  data?: unknown;
  children?: ReactNode;
};

function safeText(data: unknown) {
  if (typeof data === "string") {
    return data;
  }
  return JSON.stringify(data, null, 2);
}

export function TechnicalDetails({ title = "技术详情", data, children }: TechnicalDetailsProps) {
  return (
    <details className="technicalDetails">
      <summary>{title}</summary>
      {children ? children : <pre>{safeText(data ?? {})}</pre>}
    </details>
  );
}
