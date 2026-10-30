export type Message = {
  id: string;
  text: string;
  sender: "me" | "them";
  time: string;
  status?: "sent" | "delivered" | "read";
};

export type Contact = {
  id: string;
  name: string;
  avatar: string;
  lastSeen: string;
  online?: boolean;
};

export const nowTime = () =>
  new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

export const botContact: Contact = {
  id: "doctor",
  name: "Vaidya AI",
  avatar: "Dr",
  lastSeen: "online",
  online: true,
};

// API base URL — uses relative path in production (same CloudFront domain), falls back to localhost for dev
export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";
