import type { ReactNode } from "react";

type StepLayoutProps = {
  current: number;
  steps: string[];
  title: string;
  message: string;
  children: ReactNode;
};

export function StepLayout({ current, steps, title, message, children }: StepLayoutProps) {
  return (
    <section className="stepLayout">
      <aside className="stepRail" aria-label="设置步骤">
        <strong>首启向导</strong>
        {steps.map((step, index) => (
          <div key={step} className={index + 1 === current ? "activeStep" : index + 1 < current ? "doneStep" : ""}>
            <span>{index + 1}</span>
            <p>{step}</p>
          </div>
        ))}
      </aside>
      <article key={current} className="stepCard">
        <header>
          <span>第 {current} 步</span>
          <h2>{title}</h2>
          <p>{message}</p>
        </header>
        {children}
      </article>
    </section>
  );
}
