import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { API_BASE, botContact, nowTime, type Message } from "@/lib/chat-data";

export const Route = createFileRoute("/")({
  component: Index,
});

const SPECIALTIES = [
  { value: "general_md", label: "General Physician (MD)" },
  { value: "cardiology", label: "Cardiologist (Heart)" },
  { value: "neurology", label: "Neurologist (Brain & Nerves)" },
  { value: "dermatology", label: "Dermatologist (Skin)" },
  { value: "gastroenterology", label: "Gastroenterologist (Stomach & Digestive)" },
  { value: "orthopedic", label: "Orthopedic (Bones & Joints)" },
  { value: "ent", label: "ENT (Ear, Nose & Throat)" },
  { value: "gynecology", label: "Gynecologist (Women's Health)" },
  { value: "psychiatry", label: "Psychiatrist (Mental Health)" },
  { value: "pulmonology", label: "Pulmonologist (Lungs & Breathing)" },
  { value: "urology", label: "Urologist (Kidney & Urinary)" },
  { value: "general_surgery", label: "General Surgeon" },
  { value: "ophthalmology", label: "Ophthalmologist (Eyes)" },
];

function Index() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [chatStatus, setChatStatus] = useState<string>("registration"); // registration → loading → active → completed
  const [typing, setTyping] = useState(false);

  // Registration form state
  const [patientName, setPatientName] = useState("");
  const [patientId, setPatientId] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [city, setCity] = useState("");
  const [formError, setFormError] = useState("");

  // Register patient and start session
  const handleRegister = async () => {
    if (!patientName.trim()) { setFormError("Patient name is required"); return; }
    if (!patientId.trim()) { setFormError("Patient ID is required"); return; }
    if (!specialty) { setFormError("Please select a specialty"); return; }
    setFormError("");
    setChatStatus("loading");

    try {
      const res = await fetch(`${API_BASE}/register-patient`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hospital_id: "demo-hospital",
          patient_id: patientId.trim(),
          patient_name: patientName.trim(),
          specialty: specialty,
          city: city.trim(),
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        setFormError(data.detail || "Registration failed");
        setChatStatus("registration");
        return;
      }

      setSessionId(data.session_id);
      setChatStatus("active");
      setMessages([
        {
          id: `bot-${Date.now()}`,
          text: data.first_message,
          sender: "them",
          time: nowTime(),
        },
      ]);
    } catch (err) {
      setFormError("Unable to connect to the server");
      setChatStatus("registration");
    }
  };

  // Send chat message
  const handleSend = async (text: string) => {
    const patientMsg: Message = {
      id: `me-${Date.now()}`,
      text,
      sender: "me",
      time: nowTime(),
      status: "sent",
    };
    setMessages((prev) => [...prev, patientMsg]);
    setTyping(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      const data = await res.json();
      setTyping(false);

      // Mark all patient messages as "read" (double blue tick) since AI has seen them
      setMessages((prev) =>
        prev.map((m) =>
          m.sender === "me" ? { ...m, status: "read" as const } : m
        )
      );

      const botMsg: Message = {
        id: `bot-${Date.now()}`,
        text: data.reply,
        sender: "them",
        time: nowTime(),
      };
      setMessages((prev) => [...prev, botMsg]);

      if (data.status === "completed" || data.status === "emergency") {
        setChatStatus(data.status);
      }
    } catch (err) {
      setTyping(false);
      setMessages((prev) => [...prev, {
        id: `err-${Date.now()}`,
        text: "Connection error. Please try again.",
        sender: "them",
        time: nowTime(),
      }]);
    }
  };

  // Registration form screen
  if (chatStatus === "registration") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[image:var(--gradient-teal)] p-0 sm:p-8">
        <div className="h-screen w-full overflow-hidden bg-card sm:h-[720px] sm:w-[380px] sm:rounded-[2rem] sm:border-[10px] sm:border-foreground/85 sm:shadow-[var(--shadow-phone)]">
          <div className="flex h-full flex-col">
            <header className="flex items-center gap-3 bg-[image:var(--gradient-teal)] px-4 py-3 text-wa-teal-foreground">
              <div className="flex size-9 items-center justify-center rounded-full bg-wa-teal-foreground/25 text-xs font-semibold">
                Dr
              </div>
              <div>
                <h1 className="text-sm font-semibold">Vaidya AI</h1>
                <p className="text-[11px] opacity-80">Patient Registration</p>
              </div>
            </header>

            <div className="flex-1 overflow-y-auto px-4 py-5">
              <p className="mb-4 text-center text-sm text-muted-foreground">
                Register patient to start pre-consultation
              </p>

              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">Patient Name</label>
                  <input
                    type="text"
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    placeholder="e.g. Rahul Shah"
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-green-500"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">Patient ID</label>
                  <input
                    type="text"
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    placeholder="e.g. PAT-2024-0789"
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-green-500"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">Specialty</label>
                  <select
                    value={specialty}
                    onChange={(e) => setSpecialty(e.target.value)}
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-green-500"
                    size={1}
                    style={{ maxHeight: "200px" }}
                  >
                    <option value="">Select specialist...</option>
                    {SPECIALTIES.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">City / Locality</label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="e.g. Pune, Mumbai, Ahmedabad"
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-green-500"
                  />
                </div>

                {formError && (
                  <p className="text-xs text-red-500">{formError}</p>
                )}

                <button
                  onClick={handleRegister}
                  className="w-full rounded-lg bg-[image:var(--gradient-teal)] px-4 py-2.5 text-sm font-medium text-wa-teal-foreground shadow-sm transition-transform active:scale-[0.98]"
                >
                  Start Consultation
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // Loading screen
  if (chatStatus === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[image:var(--gradient-teal)] p-0 sm:p-8">
        <div className="h-screen w-full overflow-hidden bg-card sm:h-[720px] sm:w-[380px] sm:rounded-[2rem] sm:border-[10px] sm:border-foreground/85 sm:shadow-[var(--shadow-phone)]">
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-3 size-8 animate-spin rounded-full border-4 border-green-200 border-t-green-600" />
              <p className="text-sm text-muted-foreground">Connecting to {patientName}'s session...</p>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // Chat screen
  return (
    <main className="flex min-h-screen items-center justify-center bg-[image:var(--gradient-teal)] p-0 sm:p-8">
      <div className="h-screen w-full overflow-hidden bg-card sm:h-[720px] sm:w-[380px] sm:rounded-[2rem] sm:border-[10px] sm:border-foreground/85 sm:shadow-[var(--shadow-phone)]">
        <ChatWindow
          contact={botContact}
          messages={messages}
          onSend={handleSend}
          typing={typing}
          disabled={chatStatus === "completed" || chatStatus === "error" || chatStatus === "emergency"}
          chatStatus={chatStatus}
          sessionId={sessionId}
        />
      </div>
    </main>
  );
}
