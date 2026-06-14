import type { OperationNotice } from "../../types";

type OperationNoticeBannerProps = {
  notice: OperationNotice;
};

export function OperationNoticeBanner({ notice }: OperationNoticeBannerProps) {
  return (
    <section
      className={`operationNoticeBanner ${notice.tone}`}
      role={notice.blocking || notice.tone === "danger" ? "alert" : "status"}
      aria-live={notice.blocking || notice.tone === "danger" ? "assertive" : "polite"}
    >
      <p>{notice.message}</p>
    </section>
  );
}
