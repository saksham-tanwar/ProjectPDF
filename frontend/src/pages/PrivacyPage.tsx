import { ArrowLeft } from "lucide-react";
import { Link } from "react-router";

import { useConfig } from "../api/queries";
import { Brand } from "../components/Brand";

export function PrivacyPage() {
  const config = useConfig();
  const aiEnabled = config.data?.ai_enabled ?? true;
  const provider = config.data?.ai_provider ?? "our AI provider";

  return (
    <div className="prose-page">
      <header className="prose-header">
        <Brand />
        <Link to="/" className="button button-ghost button-small">
          <ArrowLeft size={14} aria-hidden /> Back
        </Link>
      </header>
      <article className="prose">
        <h1>Privacy notice</h1>
        <p className="muted">
          This page explains what Paperchat stores and why. The operator of this deployment should review it before launch.
        </p>

        <h2>What we store</h2>
        <ul>
          <li>Your Google account's name, email address and profile picture, used to identify your account.</li>
          <li>The PDFs you upload, stored privately so they can be processed.</li>
          <li>Text extracted from those PDFs, split into passages so your questions can be answered.</li>
          <li>A session record so you stay signed in. It expires automatically.</li>
        </ul>
        <p>Your questions and conversations are not stored on our servers. They're kept in this browser tab only.</p>

        <h2>Who can see your documents</h2>
        <p>Only your account. Documents aren't shared with other users.</p>

        {aiEnabled && (
          <>
            <h2>AI processing</h2>
            <p>
              To make documents searchable by meaning, the text extracted from each PDF is sent to {provider} to create
              embeddings (numeric representations of the text), which we store alongside the text. When you ask a
              question, your question, the recent messages in that conversation and the most relevant passages are sent
              to {provider} to generate the answer.
            </p>
          </>
        )}

        <h2>Deleting your data</h2>
        <p>
          Deleting a document removes the PDF and its extracted text. Deleting your account (from the account menu) removes
          your account, every document and all extracted text.
        </p>
      </article>
    </div>
  );
}
