import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ChevronRight,
  FileText,
  GitCompareArrows,
  ExternalLink,
  Fingerprint,
} from "lucide-react";
import { api } from "../api";
import { type Identity, type Certificate } from "@eventweave/protocol";
import {
  Status,
  Notice,
  Empty,
  PageIntro,
  kindLabels,
  statusLabels,
} from "../components/ui";

export default function EventDetail() {
  const { id } = useParams();
  const [data, setData] = useState<{
    identity: Identity;
    relations: Certificate[];
    aliases: unknown[];
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .identity(id!)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [id]);
  return (
    <div className="page">
      <Link className="back-link" to="/">
        Registry / Record
      </Link>
      {error ? (
        <Notice error>{error}</Notice>
      ) : !data ? (
        <div className="loading-state">Reading this record…</div>
      ) : (
        <>
          <PageIntro
            title={data.identity.title}
            action={<Status status={data.identity.status} />}
          >
            {kindLabels[data.identity.occurrence_type]} from{" "}
            {data.identity.issuer}. Original attribution stays with this record.
          </PageIntro>
          <div className="document-layout">
            <section>
              <div className="document-heading">
                <Fingerprint size={20} />
                <h2>Identity discriminators</h2>
              </div>
              <dl className="facts-list">
                {[
                  ["Issuer", data.identity.issuer],
                  ["Place or service", data.identity.place],
                  [
                    "Occurrence begins",
                    new Date(data.identity.interval_start).toUTCString(),
                  ],
                  [
                    "Occurrence ends",
                    new Date(data.identity.interval_end).toUTCString(),
                  ],
                  ["Official reference", data.identity.official_reference],
                  ["Original event ID", data.identity.event_id],
                  ["Canonical identity", data.identity.canonical_id],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <h2 className="subheading">Relation history</h2>
              {data.relations.length ? (
                data.relations.map((r) => (
                  <div className="relation-entry" key={r.request_id}>
                    <Status status={r.decision} />
                    <div>
                      <b>
                        {r.left} / {r.right}
                      </b>
                      <p>
                        {r.coverage
                          ? "All required discriminators inspected."
                          : "Evidence coverage remains incomplete."}
                      </p>
                      <small>
                        Generation {r.generation} / {statusLabels[r.status]}
                      </small>
                    </div>
                    <Link to={"/challenges?relation=" + r.request_id}>
                      Inspect or challenge <ChevronRight size={16} />
                    </Link>
                  </div>
                ))
              ) : (
                <Empty title="A story of its own." icon="link">
                  No finalized pair relation has been delivered for this record.
                </Empty>
              )}
              <h2 className="subheading">Alias history</h2>
              {data.aliases.length ? (
                <pre className="code-block">
                  {JSON.stringify(data.aliases, null, 2)}
                </pre>
              ) : (
                <p className="muted">
                  No alias has been published. The original identity remains
                  available.
                </p>
              )}
            </section>
            <aside className="document-margin">
              <h3>
                <FileText size={18} />
                Source notes
              </h3>
              <p>
                The exact bytes are committed. Validators retrieve the source
                independently.
              </p>
              <a
                className="source-link"
                href={data.identity.source.url}
                target="_blank"
                rel="noreferrer"
              >
                Read the original <ExternalLink size={15} />
              </a>
              <dl className="source-facts">
                <dt>Authority</dt>
                <dd>{data.identity.source.authority_id}</dd>
                <dt>Revision</dt>
                <dd>{data.identity.source.revision}</dd>
                <dt>Byte commitment</dt>
                <dd className="hash-text">{data.identity.source.raw_hash}</dd>
              </dl>
              <Link className="button button-ink" to={"/workspace?left=" + id}>
                <GitCompareArrows size={17} />
                Find a candidate
              </Link>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
