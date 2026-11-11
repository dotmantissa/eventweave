import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { usePrivy } from "@privy-io/react-auth";
import {
  FileText,
  GitCompareArrows,
  ShieldCheck,
  ExternalLink,
  Fingerprint,
} from "lucide-react";
import { request } from "../api";
import { useOperation } from "../use-operation";
import {
  Notice,
  PageIntro,
  Feedback,
  kindLabels,
  formatDate,
} from "../components/ui";
import { useEvents } from "../hooks/use-events";
import { DocketFlow } from "../components/DocketFlow";

export default function Workspace() {
  const [params] = useSearchParams();
  const { items, error } = useEvents();
  const [left, setLeft] = useState(params.get("left") || "");
  const [right, setRight] = useState(params.get("right") || "");
  const [consumer, setConsumer] = useState<"incident" | "release">("release");
  const operation = useOperation();
  const [result, setResult] = useState("");
  const [requestId, setRequestId] = useState(params.get("request") || "");
  const pair = [
    items.find((e) => e.event_id === left),
    items.find((e) => e.event_id === right),
  ];
  async function compare() {
    try {
      const token = await request<{ request_json: string }>(
        "/comparisons/prepare",
        {
          method: "POST",
          body: JSON.stringify({ left, right, consumer }),
          headers: { Authorization: "Bearer " + (await getToken()) },
        },
      );
      const receipt = await operation.run("court", "compare_records", [
        token.request_json,
      ]);
      setRequestId(JSON.parse(token.request_json).envelope.request_id);
      setResult(
        "Your request is sent. Once it finalizes, read the docket below to assess the records. Operation " +
          receipt.operation_id,
      );
    } catch (e) {
      setResult(
        e instanceof Error ? e.message : "This comparison could not be opened.",
      );
    }
  }
  const { getAccessToken: getToken } = usePrivy();
  return (
    <div className="page">
      <PageIntro title="Untangle the reports.">
        Put two records side by side. Names are clues. Evidence gets the last
        word.
      </PageIntro>
      {error && <Notice error>{error}</Notice>}
      <div className="comparison-layout">
        {[0, 1].map((index) => (
          <section className="comparison-document" key={index}>
            <div className="comparison-title">
              <FileText size={20} />
              <h2>{index === 0 ? "First record" : "Candidate record"}</h2>
            </div>
            <label className="field">
              Choose a public record
              <select
                value={index === 0 ? left : right}
                onChange={(e) =>
                  index === 0
                    ? setLeft(e.target.value)
                    : setRight(e.target.value)
                }
              >
                <option value="">Select an occurrence</option>
                {items
                  .filter((e) => e.event_id !== (index === 0 ? right : left))
                  .map((e) => (
                    <option key={e.event_id} value={e.event_id}>
                      {e.title}
                    </option>
                  ))}
              </select>
            </label>
            {pair[index] ? (
              <>
                <h3 className="comparison-event-name">{pair[index]!.title}</h3>
                <dl className="facts-list compact">
                  {[
                    ["Issuer", pair[index]!.issuer],
                    ["Place", pair[index]!.place],
                    ["Interval", formatDate(pair[index]!.interval_start)],
                    ["Type", kindLabels[pair[index]!.occurrence_type]],
                    ["Reference", pair[index]!.official_reference],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
                <a
                  className="source-link"
                  href={pair[index]!.source.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Committed source <ExternalLink size={15} />
                </a>
              </>
            ) : (
              <div className="comparison-placeholder">
                <Fingerprint size={38} />
                <p>
                  A record belongs here.
                  <br />
                  Choose one above to see its discriminators.
                </p>
              </div>
            )}
          </section>
        ))}
      </div>
      <div className="assessment-footer">
        <div>
          <label className="field">
            Evidence consumer
            <select
              value={consumer}
              onChange={(e) =>
                setConsumer(e.target.value as "incident" | "release")
              }
            >
              <option value="release">Release Evidence</option>
              <option value="incident">Incident History</option>
            </select>
          </label>
          <p>
            <ShieldCheck size={16} />
            Five mandatory attributes. Independent validator review.
          </p>
        </div>
        <button
          className="button button-primary"
          disabled={!left || !right || left === right || operation.busy}
          onClick={compare}
        >
          <GitCompareArrows size={18} />
          {operation.busy ? "Opening the docket…" : "Request comparison"}
        </button>
      </div>
      <Feedback message={result || operation.message} />
      <DocketFlow key={requestId} requestId={requestId} />
      <div className="inline-guidance">
        <h3>One useful answer is “we don’t know.”</h3>
        <p>
          Missing facts remain unknown. A shared root cause does not make two
          incidents the same. Larger merges need a complete proof for every
          pair, with at most six records.
        </p>
      </div>
    </div>
  );
}
