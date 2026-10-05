"use client";

import { useEffect, useRef, useState } from "react";
import { getImportJobStatus, importMembers, type ImportJob } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";

export default function ImportMembersPage() {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const created = await importMembers(file);
      setJob(created);
      pollRef.current = setInterval(async () => {
        const updated = await getImportJobStatus(created.id);
        setJob(updated);
        if (updated.status === "done" || updated.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      }, 2000);
    } catch {
      setError("Couldn't start the import — check the file and try again.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold">Import members</h1>
      <p className="text-sm opacity-70">
        Upload a CSV or XLSX file with columns: full_name, phone, gender, dob (YYYY-MM-DD), tags
        (comma-separated), marketing_opt_in.
      </p>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <form onSubmit={submit} className="flex items-center gap-2">
        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm"
        />
        <Button type="submit" disabled={!file || uploading}>
          {uploading ? "Starting..." : "Import"}
        </Button>
      </form>

      {job && (
        <div className="space-y-2 rounded border p-4 text-sm">
          <p>
            Status: <span className="font-medium">{job.status}</span>
          </p>
          {job.status === "done" && (
            <>
              <p>
                {job.success_count} of {job.total_rows} rows imported successfully.
              </p>
              {job.error_report && (
                <a
                  href={job.error_report}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Download error report
                </a>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
