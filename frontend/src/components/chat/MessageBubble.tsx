import { Check, CheckCheck } from "lucide-react";
import type { Message } from "@/lib/chat-data";
import { cn } from "@/lib/utils";

export function MessageBubble({ message }: { message: Message }) {
  // "me" = patient = LEFT side (green/outgoing bubble)
  // "them" = bot/doctor = RIGHT side (white/incoming bubble)
  const isPatient = message.sender === "me";

  return (
    <div className={cn("flex w-full px-3", isPatient ? "justify-start" : "justify-end")}>
      <div
        className={cn(
          "relative max-w-[78%] rounded-2xl px-3 py-2 text-[13px] leading-snug shadow-[var(--shadow-bubble)]",
          isPatient
            ? "rounded-bl-md bg-bubble-out text-bubble-out-foreground"
            : "rounded-br-md bg-bubble-in text-bubble-in-foreground",
        )}
      >
        <p className="whitespace-pre-wrap break-words pb-2.5 pr-10">{message.text}</p>
        <span
          className={cn(
            "absolute bottom-1.5 right-2.5 flex items-center gap-0.5 text-[10px] opacity-60",
          )}
        >
          {message.time}
          {isPatient &&
            (message.status === "read" ? (
              <CheckCheck className="size-3 text-tick opacity-100" />
            ) : message.status === "delivered" ? (
              <CheckCheck className="size-3" />
            ) : (
              <Check className="size-3" />
            ))}
        </span>
      </div>
    </div>
  );
}
