import type { ReactNode } from "react";
import { TechnicalDetails } from "./TechnicalDetails";

type Action = {
  label: string;
  onClick: () => void;
};

type ErrorWithActionProps = {
  title: string;
  message: string;
  suggestion?: string;
  primaryAction?: Action;
  secondaryActions?: Action[];
  technicalDetails?: unknown;
  children?: ReactNode;
};

export function ErrorWithAction({
  title,
  message,
  suggestion,
  primaryAction,
  secondaryActions = [],
  technicalDetails,
  children
}: ErrorWithActionProps) {
  return (
    <section className="errorWithAction" role="alert">
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
        {suggestion && <p className="nextStep">{suggestion}</p>}
      </div>
      {children}
      <div className="actionRow">
        {primaryAction && (
          <button type="button" onClick={primaryAction.onClick}>
            {primaryAction.label}
          </button>
        )}
        {secondaryActions.map((action) => (
          <button key={action.label} type="button" className="secondaryButton" onClick={action.onClick}>
            {action.label}
          </button>
        ))}
      </div>
      {technicalDetails !== undefined && <TechnicalDetails data={technicalDetails} />}
    </section>
  );
}
