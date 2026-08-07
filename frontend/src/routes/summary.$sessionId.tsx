import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { API_BASE } from "@/lib/chat-data";

export const Route = createFileRoute("/summary/$sessionId")({
  component: SummaryPage,
});

type SummaryData = {
  hospital_id: string;
  patient_id: string;
  patient_name: string;
  session_id: string;
  specialty: string;
  status: string;
  summary: Record<string, unknown>;
  conversation_turns: number;
  created_at: string;
  completed_at: string | null;
};

function SummaryPage() {
  const { sessionId } = Route.useParams();
  const [data, setData] = useState<SummaryData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/session/${sessionId}/summary`)
      .then((res) => {
        if (!res.ok) throw new Error("Summary not available");
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [sessionId]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="mx-auto mb-3 size-8 animate-spin rounded-full border-4 border-green-200 border-t-green-600" />
          <p className="text-sm text-gray-500">Loading summary...</p>
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md rounded-xl bg-white p-8 text-center shadow-lg">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-red-100">
            <span className="text-xl">!</span>
          </div>
          <h2 className="text-lg font-semibold text-gray-800">Summary Not Available</h2>
          <p className="mt-2 text-sm text-gray-500">{error || "Could not load the summary."}</p>
          <a href="/" className="mt-4 inline-block text-sm text-green-600 underline">Back to home</a>
        </div>
      </main>
    );
  }

  const summary = data.summary as Record<string, unknown>;
  const specialtyLabel = formatSpecialty(data.specialty);
  const createdDate = formatDate(data.created_at);
  const completedDate = data.completed_at ? formatDate(data.completed_at) : null;

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-6 rounded-xl bg-gradient-to-r from-green-600 to-teal-600 p-6 text-white shadow-lg">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-white/20 text-sm font-bold">
              Dr
            </div>
            <div>
              <h1 className="text-lg font-bold">Pre-Consult AI Summary</h1>
              <p className="text-sm text-green-100">Doctor's Pre-Consultation Report</p>
            </div>
          </div>
        </div>

        {/* Patient Info Card */}
        <div className="mb-4 rounded-xl bg-white p-5 shadow-sm">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <InfoItem label="Patient" value={data.patient_name} />
            <InfoItem label="Patient ID" value={data.patient_id} />
            <InfoItem label="Specialty" value={specialtyLabel} />
            <InfoItem label="Status" value={<StatusBadge status={data.status} />} />
            <InfoItem label="Date" value={createdDate} />
            <InfoItem label="Consultation Turns" value={String(data.conversation_turns)} />
          </div>
        </div>

        {/* Clinical Summary */}
        {summary.parse_error ? (
          <div className="mb-4 rounded-xl bg-white p-5 shadow-sm">
            <SectionTitle title="Clinical Narrative" />
            <p className="text-sm text-gray-700 whitespace-pre-wrap">
              {String(summary.clinical_narrative || "")}
            </p>
          </div>
        ) : (
          <>
            {summary.chief_complaint && (
              <SummaryCard title="Chief Complaint" content={String(summary.chief_complaint)} />
            )}

            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {summary.onset && <MiniCard label="Onset" value={String(summary.onset)} />}
              {summary.duration && <MiniCard label="Duration" value={String(summary.duration)} />}
              {summary.severity && <MiniCard label="Severity" value={String(summary.severity)} />}
              {summary.location && <MiniCard label="Location" value={String(summary.location)} />}
              {summary.character && <MiniCard label="Character" value={String(summary.character)} />}
            </div>

            {renderList("Associated Symptoms", summary.associated_symptoms)}
            {renderList("Aggravating Factors", summary.aggravating_factors)}
            {renderList("Relieving Factors", summary.relieving_factors)}
            {renderList("Past Medical History", summary.past_medical_history)}
            {renderList("Current Medications", summary.current_medications)}
            {renderList("Allergies", summary.allergies)}

            {summary.previous_episodes && (
              <SummaryCard title="Previous Episodes" content={String(summary.previous_episodes)} />
            )}
            {summary.recent_investigations && (
              <SummaryCard title="Recent Investigations" content={String(summary.recent_investigations)} />
            )}
            {summary.lifestyle && (
              <SummaryCard title="Lifestyle" content={String(summary.lifestyle)} />
            )}
            {summary.patient_concerns && (
              <SummaryCard title="Patient Concerns" content={String(summary.patient_concerns)} />
            )}

            {renderList("Red Flags", summary.red_flags, "red")}
            {renderList("Information Gaps", summary.information_gaps, "amber")}
          </>
        )}

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-gray-400">
          <p>Generated by Pre-Consult AI | Session: {data.session_id.slice(0, 8)}...</p>
          {completedDate && <p>Completed: {completedDate}</p>}
        </div>
      </div>
    </main>
  );
}

// --- Helper Components ---

function InfoItem({ label, value }: { label: string; value: string | React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-400 uppercase">{label}</p>
      <p className="mt-0.5 font-medium text-gray-800">{typeof value === "string" ? value : value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-green-100 text-green-800",
    emergency: "bg-red-100 text-red-800",
    active: "bg-blue-100 text-blue-800",
    expired: "bg-gray-100 text-gray-800",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] || colors.active}`}>
      {status === "completed" ? "Completed" : status === "emergency" ? "EMERGENCY" : status}
    </span>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h3 className="mb-2 text-sm font-semibold text-gray-600 uppercase tracking-wide">{title}</h3>;
}

function SummaryCard({ title, content }: { title: string; content: string }) {
  return (
    <div className="mb-4 rounded-xl bg-white p-5 shadow-sm">
      <SectionTitle title={title} />
      <p className="text-sm text-gray-700">{content}</p>
    </div>
  );
}

function MiniCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white p-4 shadow-sm">
      <p className="text-xs font-medium text-gray-400 uppercase">{label}</p>
      <p className="mt-1 text-sm font-medium text-gray-700">{value}</p>
    </div>
  );
}

function renderList(title: string, items: unknown, color: "default" | "red" | "amber" = "default") {
  if (!items || !Array.isArray(items) || items.length === 0) return null;

  const bgColor = color === "red" ? "bg-red-50" : color === "amber" ? "bg-amber-50" : "bg-white";
  const dotColor = color === "red" ? "bg-red-400" : color === "amber" ? "bg-amber-400" : "bg-green-400";
  const titleColor = color === "red" ? "text-red-700" : color === "amber" ? "text-amber-700" : "text-gray-600";

  return (
    <div className={`mb-4 rounded-xl ${bgColor} p-5 shadow-sm`}>
      <h3 className={`mb-2 text-sm font-semibold uppercase tracking-wide ${titleColor}`}>{title}</h3>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
            <span className={`mt-1.5 size-2 shrink-0 rounded-full ${dotColor}`} />
            {String(item)}
          </li>
        ))}
      </ul>
    </div>
  );
}

// --- Utility Functions ---

function formatSpecialty(specialty: string): string {
  const map: Record<string, string> = {
    general_md: "General Physician (MD)",
    cardiology: "Cardiologist",
    neurology: "Neurologist",
    dermatology: "Dermatologist",
    gastroenterology: "Gastroenterologist",
    orthopedic: "Orthopedic",
    ent: "ENT (Ear, Nose & Throat)",
    gynecology: "Gynecologist",
  };
  return map[specialty] || specialty;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
