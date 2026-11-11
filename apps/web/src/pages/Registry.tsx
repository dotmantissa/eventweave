import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  Search,
  Plus,
  ChevronRight,
  Check,
  FileText,
  GitCompareArrows,
  ShieldCheck,
  Clock,
  X,
  RefreshCw,
  Fingerprint,
  ArrowUpRight,
  Layers,
} from "lucide-react";
import {
  Status,
  Notice,
  Empty,
  kindLabels,
  formatDate,
} from "../components/ui";
import { useEvents } from "../hooks/use-events";

export default function Registry() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const kind = params.get("kind") || "";
  const [selection, setSelection] = useState<string[]>([]);
  const { items, loading, error, total, reload } = useEvents(q, kind);
  const navigate = useNavigate();
  function update(key: string, value: string) {
    setParams((p) => {
      if (value) p.set(key, value);
      else p.delete(key);
      return p;
    });
  }
  function select(id: string) {
    setSelection((s) =>
      s.includes(id)
        ? s.filter((x) => x !== id)
        : s.length < 2
          ? [...s, id]
          : s,
    );
  }
  return (
    <div className="registry-page">
      <section className="registry-opening">
        <div className="opening-body">
          <h1>
            Names change.
            <br />
            History <span>shouldn’t.</span>
          </h1>
          <p className="hero-copy">
            A release gets renamed. An incident gets reported twice.
            <br className="desktop-break" /> Keep the evidence connected,
            without losing the plot.
          </p>
          <form
            className="hero-search"
            onSubmit={(e) => e.preventDefault()}
            role="search"
          >
            <Search size={21} />
            <input
              aria-label="Search public events"
              placeholder="Find an event, issuer or official reference"
              value={q}
              onChange={(e) => update("q", e.target.value)}
            />
            {q && (
              <button
                type="button"
                className="icon-button"
                onClick={() => update("q", "")}
                aria-label="Clear search"
              >
                <X size={17} />
              </button>
            )}
            <button className="search-submit" type="submit">
              Search
            </button>
          </form>
          <div className="search-caption">
            <Fingerprint size={15} />
            <span>
              Public records. Shared identities. Every source keeps its credit.
            </span>
          </div>
        </div>
        <aside className="evidence-margin">
          <div className="margin-title">
            <FileText size={20} />
            <span>A little context</span>
          </div>
          <p>
            Same story?
            <br />
            <strong>Let the evidence say.</strong>
          </p>
          <div className="margin-annotation">
            <GitCompareArrows size={18} />
            <div>
              <b>Same occurrence</b>
              <span>Different reports, one identity.</span>
            </div>
          </div>
          <div className="margin-annotation">
            <Layers size={18} />
            <div>
              <b>Distinct events</b>
              <span>A familiar name can hide a new incident.</span>
            </div>
          </div>
          <div className="margin-annotation">
            <Clock size={18} />
            <div>
              <b>Room for uncertainty</b>
              <span>No evidence, no forced answer.</span>
            </div>
          </div>
          <Link to="/guide">
            Meet the registry <ChevronRight size={16} />
          </Link>
        </aside>
      </section>
      <section className="registry-index" aria-labelledby="registry-heading">
        <div className="section-heading">
          <div>
            <h2 id="registry-heading">The public record</h2>
            <p>Find the occurrence behind the headline.</p>
          </div>
          <Link className="button button-primary" to="/new">
            <Plus size={18} />
            Register an event
          </Link>
        </div>
        <div className="registry-toolbar">
          <div className="filter-tabs" role="group" aria-label="Event type">
            {[
              ["", "All events"],
              ["release", "Releases"],
              ["security_incident", "Security"],
              ["operational_notice", "Operations"],
            ].map(([value, label]) => (
              <button
                key={value}
                aria-pressed={kind === value}
                className={kind === value ? "selected" : ""}
                onClick={() => update("kind", value)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="index-summary">
            <span>
              {loading
                ? "Reading the registry…"
                : `${total} ${total === 1 ? "record" : "records"}`}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh registry"
              onClick={reload}
            >
              <RefreshCw size={15} />
            </button>
          </div>
        </div>
        {error ? (
          <Notice error>
            {error}{" "}
            <button className="text-button" onClick={reload}>
              Try again
            </button>
          </Notice>
        ) : loading ? (
          <div className="loading-state" role="status">
            <RefreshCw size={20} />
            Reading public contract state…
          </div>
        ) : items.length ? (
          <>
            <div className="ledger-head">
              <span>Occurrence</span>
              <span>When & where</span>
              <span>Identity</span>
              <span>Compare</span>
            </div>
            <div className="event-ledger">
              {items.map((event) => (
                <article
                  className={
                    "event-row " +
                    (selection.includes(event.event_id) ? "is-selected" : "")
                  }
                  key={event.event_id}
                >
                  <Link
                    className="event-title"
                    to={"/events/" + event.event_id}
                  >
                    <span className="record-icon">
                      <FileText size={20} />
                    </span>
                    <div>
                      <span className="record-kind">
                        {kindLabels[event.occurrence_type]}
                      </span>
                      <h3>{event.title}</h3>
                      <span className="record-reference">
                        {event.issuer}{" "}
                        <span className="reference-divider">/</span>{" "}
                        {event.official_reference}
                      </span>
                    </div>
                  </Link>
                  <div className="event-when">
                    <span>{formatDate(event.interval_start)}</span>
                    <small>{event.place}</small>
                  </div>
                  <div className="event-identity">
                    <Status status={event.status} />
                    <small>
                      {event.members.length > 1
                        ? `${event.members.length} linked records`
                        : "Original record"}
                    </small>
                  </div>
                  <button
                    className={
                      "compare-select " +
                      (selection.includes(event.event_id) ? "checked" : "")
                    }
                    onClick={() => select(event.event_id)}
                    aria-pressed={selection.includes(event.event_id)}
                    aria-label={"Select " + event.title + " for comparison"}
                    disabled={
                      !selection.includes(event.event_id) &&
                      selection.length === 2
                    }
                  >
                    {selection.includes(event.event_id) ? (
                      <Check size={17} />
                    ) : (
                      <Plus size={17} />
                    )}
                  </button>
                </article>
              ))}
            </div>
          </>
        ) : (
          <Empty
            title={
              q
                ? "No thread found. Yet."
                : "The registry is ready for its first record."
            }
          >
            {q
              ? "Try an issuer, service name or official reference. The right words make all the difference."
              : "Register a public release, disclosed incident or official notice. Nothing here is filled with pretend history."}
          </Empty>
        )}
        {selection.length > 0 && (
          <div className="selection-bar" role="status">
            <span>
              <GitCompareArrows size={18} />
              {selection.length === 1
                ? "One selected. Pick another record to compare."
                : "Two records, one question. Are they the same event?"}
            </span>
            <div>
              <button className="text-button" onClick={() => setSelection([])}>
                Clear
              </button>
              <button
                className="button button-ink"
                disabled={selection.length !== 2}
                onClick={() =>
                  navigate(
                    "/workspace?left=" +
                      selection[0] +
                      "&right=" +
                      selection[1],
                  )
                }
              >
                Compare records <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </section>
      <section className="registry-footnote">
        <ShieldCheck size={25} />
        <div>
          <h3>A shared identity. Your own rules.</h3>
          <p>
            EventWeave connects records. Your application decides what happens
            next.
          </p>
        </div>
        <Link to="/applications">
          See the integrations <ArrowUpRight size={17} />
        </Link>
      </section>
    </div>
  );
}
