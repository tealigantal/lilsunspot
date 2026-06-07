import type { ReactNode } from "react";

type PrimaryActionPanelProps = {
  title: string;
  message: string;
  primaryLabel: string;
  onPrimary: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  busy?: boolean;
  children?: ReactNode;
};

export function PrimaryActionPanel({
  title,
  message,
  primaryLabel,
  onPrimary,
  secondaryLabel,
  onSecondary,
  busy = false,
  children
}: PrimaryActionPanelProps) {
  return (
    <section className="primaryActionPanel">
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {children}
      <div className="actionRow">
        <button type="button" onClick={onPrimary} disabled={busy}>
          {primaryLabel}
        </button>
        {secondaryLabel && onSecondary && (
          <button type="button" className="secondaryButton" onClick={onSecondary} disabled={busy}>
            {secondaryLabel}
          </button>
        )}
      </div>
    </section>
  );
}
