import { useEffect, useRef, useState } from "react";
import {
  Camera,
  Mic,
  MoreVertical,
  Paperclip,
  Phone,
  Send,
  Smile,
  Video,
} from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import type { Contact, Message } from "@/lib/chat-data";

type Props = {
  contact: Contact;
  messages: Message[];
  onSend: (text: string) => void;
  typing?: boolean;
  disabled?: boolean;
  chatStatus?: string;
  sessionId?: string;
};

export function ChatWindow({ contact, messages, onSend, typing = false, disabled = false, chatStatus, sessionId }: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  useEffect(() => {
    if (!disabled) inputRef.current?.focus();
  }, [disabled]);

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    setDraft("");
    inputRef.current?.focus();
  };

  return (
    <div className="flex h-full flex-col bg-chat-bg">
      {/* Header */}
      <header className="flex items-center gap-3 bg-[image:var(--gradient-teal)] px-3 py-2.5 text-wa-teal-foreground">
        <div className="relative">
          <div className="flex size-9 items-center justify-center rounded-full bg-wa-teal-foreground/25 text-xs font-semibold">
            {contact.avatar}
          </div>
          {contact.online && (
            <span className="absolute bottom-0 right-0 size-2.5 rounded-full border-2 border-wa-teal bg-bubble-out" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold">{contact.name}</h1>
          <p className="truncate text-[11px] opacity-80">
            {typing ? "typing…" : contact.online ? "online" : contact.lastSeen}
          </p>
        </div>
        <Video className="size-5 opacity-90" />
        <Phone className="size-[18px] opacity-90" />
        <MoreVertical className="size-5 opacity-90" />
      </header>

      {/* Messages */}
      <div className="flex-1 space-y-1.5 overflow-y-auto py-3">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {typing && (
          <div className="flex justify-end px-3">
            <div className="flex gap-1 rounded-2xl rounded-br-md bg-bubble-in px-3 py-2.5 shadow-[var(--shadow-bubble)]">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="size-1.5 animate-bounce rounded-full bg-bubble-in-foreground/40"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Completion banner */}
      {chatStatus === "completed" && (
        <div className="bg-green-100 px-4 py-2 text-center text-xs text-green-800">
          <p>Consultation complete. The doctor will review your information shortly.</p>
          <a
            href={`/api/v1/session/${sessionId}/summary`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-block underline font-medium text-green-900"
          >
            View Doctor Summary
          </a>
        </div>
      )}
      {chatStatus === "emergency" && (
        <div className="bg-red-100 px-4 py-2 text-center text-xs text-red-800">
          Please inform the hospital staff immediately.
        </div>
      )}

      {/* Input */}
      <form onSubmit={send} className="flex items-center gap-2 px-2.5 py-2.5">
        <div className="flex flex-1 items-center gap-2 rounded-full bg-card px-3 py-2 shadow-[var(--shadow-bubble)]">
          <Smile className="size-5 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={disabled ? "Chat ended" : "Message"}
            aria-label="Message"
            disabled={disabled}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
          />
          <Paperclip className="size-[18px] shrink-0 text-muted-foreground" />
          <Camera className="size-[18px] shrink-0 text-muted-foreground" />
        </div>
        <button
          type="submit"
          disabled={disabled || !draft.trim()}
          aria-label={draft.trim() ? "Send message" : "Record voice message"}
          className="flex size-11 shrink-0 items-center justify-center rounded-full bg-[image:var(--gradient-teal)] text-wa-teal-foreground shadow-[var(--shadow-bubble)] transition-transform active:scale-95 disabled:opacity-50"
        >
          {draft.trim() ? <Send className="size-5" /> : <Mic className="size-5" />}
        </button>
      </form>
    </div>
  );
}
