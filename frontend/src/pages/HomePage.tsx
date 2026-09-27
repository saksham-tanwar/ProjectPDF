import { BookOpenText, Quote, ShieldCheck } from "lucide-react";

import { useConfig, useMe } from "../api/queries";
import { UploadDropzone } from "../components/UploadDropzone";

export function HomePage() {
  const { data: user } = useMe();
  const config = useConfig();
  const firstName = user?.name.split(" ")[0];

  return (
    <div className="home">
      <section className="home-hero">
        <p className="eyebrow">New document</p>
        <h1>{firstName ? `What are we reading today, ${firstName}?` : "What are we reading today?"}</h1>
        <p className="lede">Upload a PDF, then ask questions. Every answer links back to the pages it came from.</p>
        <UploadDropzone maxMb={config.data?.max_upload_mb ?? 25} />
      </section>

      <ul className="feature-list">
        <li>
          <BookOpenText size={20} aria-hidden />
          <div>
            <strong>Reads the text layer</strong>
            <span>Works with PDFs that have selectable text. Scanned images aren't supported yet.</span>
          </div>
        </li>
        <li>
          <Quote size={20} aria-hidden />
          <div>
            <strong>Answers with sources</strong>
            <span>
              {config.data?.ai_enabled === false
                ? "Returns the most relevant passages with page numbers."
                : "Answers cite the pages they rely on, so you can check them."}
            </span>
          </div>
        </li>
        <li>
          <ShieldCheck size={20} aria-hidden />
          <div>
            <strong>Private to you</strong>
            <span>Only your account can see your documents. Delete them any time.</span>
          </div>
        </li>
      </ul>
    </div>
  );
}
