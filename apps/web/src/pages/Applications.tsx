import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronDown,
  FileText,
  ShieldCheck,
  ExternalLink,
  BookOpen,
} from "lucide-react";
import { request } from "../api";
import { Notice, PageIntro } from "../components/ui";

export default function Applications() {
  const [data, setData] = useState<{
    items: {
      name: string;
      address: string;
      owner: string;
      stats: { accepted_count: number; held_count: number; capacity: number };
      configuration: {
        unresolved: string;
        policy_id: string;
        consequence_digest: string;
      };
    }[];
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    request<typeof data>("/applications")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <div className="page">
      <PageIntro title="Shared evidence. Separate judgement.">
        Two independently owned applications consume finalized identities. Each
        keeps its own rules and original references.
      </PageIntro>
      {error ? (
        <Notice error>{error}</Notice>
      ) : !data ? (
        <div className="loading-state">Reading consumer contracts…</div>
      ) : (
        data.items.map((item) => (
          <section className="application-row" key={item.address}>
            <div className="application-icon">
              {item.name === "Incident History" ? (
                <ShieldCheck size={30} />
              ) : (
                <FileText size={30} />
              )}
            </div>
            <div className="application-description">
              <h2>{item.name}</h2>
              <p>
                {item.name === "Incident History"
                  ? "Count public incidents without letting a rename wash away their history."
                  : "Reuse committed release and operational evidence without borrowing somebody else’s outcome rules."}
              </p>
              <a
                href={"https://studio.genlayer.com/contracts/" + item.address}
                target="_blank"
                rel="noreferrer"
                className="source-link"
              >
                Inspect contract <ExternalLink size={14} />
              </a>
              <details>
                <summary>
                  Ownership and policy <ChevronDown size={14} />
                </summary>
                <dl className="source-facts">
                  <dt>Independent owner</dt>
                  <dd className="hash-text">{item.owner}</dd>
                  <dt>Policy</dt>
                  <dd>{item.configuration.policy_id}</dd>
                  <dt>Consequence commitment</dt>
                  <dd className="hash-text">
                    {item.configuration.consequence_digest}
                  </dd>
                </dl>
              </details>
            </div>
            <div className="application-stats">
              <div>
                <b>{item.stats.accepted_count}</b>
                <span>accepted identities</span>
              </div>
              <div>
                <b>{item.stats.held_count}</b>
                <span>reserved references</span>
              </div>
            </div>
          </section>
        ))
      )}
      <div className="inline-guidance">
        <h3>Unknown stays visible in both applications.</h3>
        <p>
          An unresolved relation reserves its reference without granting
          evidence reuse. A duplicate callback is acknowledged once. A stale
          certificate can’t remove a newer restriction.
        </p>
        <Link className="source-link" to="/guide">
          Explore the public API <BookOpen size={15} />
        </Link>
      </div>
    </div>
  );
}
