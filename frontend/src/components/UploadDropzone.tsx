import { useQueryClient } from "@tanstack/react-query";
import { CircleAlert, FileUp, X } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router";

import { api } from "../api/client";
import { keys } from "../api/queries";
import type { PaperDocument } from "../api/types";
import { formatBytes, validatePdf } from "../lib/format";

type UploadState =
  | { phase: "idle"; error?: string }
  | { phase: "uploading"; file: File; progress: number };

export function UploadDropzone({ maxMb }: { maxMb: number }) {
  const [state, setState] = useState<UploadState>({ phase: "idle" });
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => () => abortRef.current?.abort(), []);

  async function start(file: File | undefined) {
    if (!file || state.phase === "uploading") return;
    const problem = validatePdf(file, maxMb);
    if (problem) {
      setState({ phase: "idle", error: problem });
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setState({ phase: "uploading", file, progress: 0 });
    try {
      const document = await api.uploadDocument(
        file,
        (progress) => setState({ phase: "uploading", file, progress }),
        controller.signal,
      );
      queryClient.setQueryData<PaperDocument[]>(keys.documents, (current) => [document, ...(current ?? [])]);
      queryClient.setQueryData(keys.document(document.id), document);
      navigate(`/documents/${document.id}`);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setState({ phase: "idle" });
      } else {
        setState({ phase: "idle", error: error instanceof Error ? error.message : "Upload failed." });
      }
    } finally {
      abortRef.current = null;
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void start(event.dataTransfer.files[0]);
  }

  if (state.phase === "uploading") {
    const percent = Math.round(state.progress * 100);
    return (
      <div className="dropzone dropzone-busy">
        <div className="upload-progress">
          <FileUp size={28} aria-hidden className="dropzone-icon" />
          <div className="upload-progress-text">
            <strong title={state.file.name}>{state.file.name}</strong>
            <span>
              {percent < 100 ? `Uploading · ${percent}%` : "Upload complete · starting to read"} · {formatBytes(state.file.size)}
            </span>
          </div>
          <button type="button" className="icon-button" onClick={() => abortRef.current?.abort()} aria-label="Cancel upload">
            <X size={18} aria-hidden />
          </button>
        </div>
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Upload progress">
          <div className="progress-bar" style={{ width: `${percent}%` }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <label
        className={`dropzone${dragging ? " dropzone-active" : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false);
        }}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="visually-hidden"
          onChange={(event) => void start(event.target.files?.[0])}
        />
        <FileUp size={32} aria-hidden className="dropzone-icon" />
        <strong>Drop a PDF here, or click to browse</strong>
        <span>Text-based PDFs up to {maxMb} MB</span>
      </label>
      {state.error && (
        <p className="notice notice-error dropzone-error" role="alert">
          <CircleAlert size={16} aria-hidden /> {state.error}
        </p>
      )}
    </div>
  );
}
