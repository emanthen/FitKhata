"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { getImportJobStatus, importMembers, type ImportJob } from "@fitkhata/api-client";
import { CircleCheck, FileSpreadsheet, Loader2, TriangleAlert, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const IMPORT_STATUS_KEY: Record<string, string> = {
  pending: "membersImportStatusPending",
  running: "membersImportStatusRunning",
  done: "membersImportStatusDone",
  failed: "membersImportStatusFailed",
};

export default function ImportMembersPage() {
  const t = useTranslations("admin");
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
      setError(t("membersImportStartError"));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("membersImportTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("membersImportColumnsHint")}</p>
      </div>

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <Card>
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <label
              htmlFor="import-file"
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-input px-4 py-5 text-sm transition-colors hover:border-ring hover:bg-muted/50"
            >
              <FileSpreadsheet size={20} strokeWidth={1.75} className="shrink-0 text-muted-foreground" />
              <span className="text-foreground/80">
                {file ? file.name : t("membersImportChooseFile")}
              </span>
              <input
                id="import-file"
                type="file"
                accept=".csv,.xlsx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
            </label>
            <Button type="submit" disabled={!file || uploading} className="self-start">
              {uploading ? (
                <Loader2 size={15} strokeWidth={2} className="animate-spin" data-icon="inline-start" />
              ) : (
                <Upload size={15} strokeWidth={2} data-icon="inline-start" />
              )}
              {uploading ? t("membersImportStarting") : t("membersImportAction")}
            </Button>
          </form>
        </CardContent>
      </Card>

      {job && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {t("membersImportStatusTitle")}
              <Badge variant={job.status === "failed" ? "destructive" : "secondary"}>
                {job.status === "done" && <CircleCheck size={11} strokeWidth={2} data-icon="inline-start" />}
                {t(IMPORT_STATUS_KEY[job.status] ?? "membersImportStatusPending")}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {job.status === "done" && (
              <div className="space-y-2 text-sm">
                <p className="font-dashboard-mono">
                  {t("membersImportRowsSummary", {
                    success: job.success_count,
                    total: job.total_rows,
                  })}
                </p>
                {job.error_report && (
                  <a
                    href={job.error_report}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-primary hover:underline"
                  >
                    {t("membersImportDownloadErrorReport")}
                  </a>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
