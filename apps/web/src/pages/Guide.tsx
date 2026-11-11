import { BookOpen, Unplug } from "lucide-react";
import { PageIntro } from "../components/ui";

export default function Guide() {
  return (
    <div className="page guide-page">
      <PageIntro title="A name isn’t an identity.">
        A small field guide to shared occurrences, honest uncertainty and
        records that survive a correction.
      </PageIntro>
      <div className="document-layout">
        <article className="guide-copy">
          <h2>Start with the occurrence</h2>
          <p>
            EventWeave looks at the issuer, place, interval, occurrence type and
            official references. A renamed report can describe the same
            incident. Two outages at the same service can be completely
            different events.
          </p>
          <h2>Let the sources do their work</h2>
          <p>
            An authorized principal commits the public record and its exact
            bytes. Validators retrieve those records independently, inspect
            contrary facts and compare every mandatory identity attribute. A
            missing fact remains unknown. Shared root cause lives in a separate
            relation.
          </p>
          <h2>Merge with the whole picture</h2>
          <p>
            A combined cluster can contain six records. Every pair needs
            complete support. A known distinct relation stops a transitive
            merge, even if one other pair looks wonderfully convincing.
          </p>
          <h2>Correct without erasing</h2>
          <p>
            A successor relation restricts the mistaken merge and invalidates
            future aliases. Consumer references keep their original attribution.
            Recovery brings the original identities back before fresh evidence
            can authorize reuse.
          </p>
          <h2>Build on the public API</h2>
          <p>
            Search is an index. Lookup shows decisive contract state and
            delivered certificates. Only authenticated finalized messages
            authorize consumer actions.
          </p>
          <pre className="code-block">{`GET /api/events?q=issuer\nGET /api/events/{event_id}\nGET /api/relations/{request_id}\nGET /api/applications\nGET /api/config`}</pre>
          <p>
            Signed writes require an email session and an embedded signing
            account. Request schemas and runnable examples live in the
            repository.
          </p>
          <a
            className="button button-ink"
            href="https://github.com/dotmantissa/corrigenda"
            target="_blank"
            rel="noreferrer"
          >
            <BookOpen size={17} />
            Read the integration guide
          </a>
        </article>
        <aside className="document-margin">
          <h3>
            <Unplug size={18} />
            Where the boundary sits
          </h3>
          <p>
            EventWeave cannot discover undisclosed incidents or prove the
            identity of every report.
          </p>
          <p>
            It does not decide compensation, financial settlement or whether an
            application should accept an outcome.
          </p>
          <p>And it won’t pretend a neat JSON response makes a verdict true.</p>
        </aside>
      </div>
    </div>
  );
}
