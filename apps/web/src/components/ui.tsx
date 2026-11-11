import { type ReactNode } from "react";
import { Link2, AlertCircle, Inbox } from "lucide-react";

export const kindLabels: Record<string, string> = {
  release: "Software release",
  security_incident: "Security incident",
  operational_notice: "Operational notice",
};

export const statusLabels: Record<string, string> = {
  pending: "Pending",
  accepted: "Accepted",
  finalized: "Finalized",
  unresolved: "Unresolved",
  timeout: "Timed out",
  superseded: "Superseded",
  quarantined: "Under review",
  delivery_failed: "Delivery failed",
  SAME: "Same event",
  DISTINCT: "Distinct events",
  UNKNOWN: "Still unknown",
};

export const formatDate = (v: string) =>
  new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(v));

export function Mark({ small = false }: { small?: boolean }) {
  return (
    <img
      className={small ? "brand-mark small" : "brand-mark"}
      src="/favicon.svg"
      alt=""
    />
  );
}

export function Status({ status }: { status: string }) {
  return (
    <span className={"status status-" + status}>
      <span className="status-dot" />
      {statusLabels[status] || status}
    </span>
  );
}

export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      role={error ? "alert" : "status"}
      className={"notice " + (error ? "notice-error" : "")}
    >
      <AlertCircle size={18} />
      <span>{children}</span>
    </div>
  );
}

export function Empty({
  title,
  children,
  icon = "inbox",
}: {
  title: string;
  children: ReactNode;
  icon?: string;
}) {
  return (
    <div className="empty">
      <div className="empty-symbol">
        {icon === "link" ? <Link2 size={28} /> : <Inbox size={28} />}
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function PageIntro({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="page-intro">
      <div>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {action}
    </div>
  );
}

export function Feedback({ message }: { message: string }) {
  return message ? <Notice>{message}</Notice> : null;
}
