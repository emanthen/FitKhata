export type CheckinSource = "biometric" | "rfid" | "qr_gate" | "front_desk_manual";

export interface PendingCheckin {
  client_uuid: string;
  member_code: string;
  check_in_at: string; // ISO 8601
  source: CheckinSource;
  created_at: string; // ISO 8601, when this row was first queued locally
}

export interface DeadCheckin extends PendingCheckin {
  reason: string;
  dead_at: string;
}

export interface BatchCheckinResult {
  accepted: string[];
  duplicates: string[];
  rejected: { client_uuid: string; reason: string }[];
}

export interface SnapshotMember {
  member_code: string;
  member_id: number;
  status: string;
  expiry_date: string | null; // ISO date, "YYYY-MM-DD"
  updated_at: string;
}
