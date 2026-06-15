"use client";

import { useEffect } from "react";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ChatInput } from "@/components/chat/chat-input";
import { PegasusLogo } from "@/components/ui/pegasus-logo";
import { useChatStore } from "@/lib/stores/chat-store";
import { useThemeStore, applyTheme } from "@/lib/stores/theme-store";
import * as api from "@/lib/api/client";

/**
 * Full-screen PegasusAI Chat, no studio chrome — meant to be embedded as an
 * iframe panel inside JupyterLab (same origin, so the gateway session cookie
 * and /api calls work). Mirrors ChatSidebar's history load.
 */
export default function ChatEmbedPage() {
  const loadHistory = useChatStore((s) => s.loadHistory);
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    api
      .getChatHistory()
      .then((data) => {
        const msgs = data.messages.map((m, i) => ({
          id: `hist-${i}`,
          role: m.role as "user" | "assistant",
          content: m.content,
          agentId: m.agent_id ?? undefined,
          createdAt: m.created_at ?? undefined,
        }));
        if (msgs.length > 0) loadHistory(msgs);
      })
      .catch(() => {});
  }, [loadHistory]);

  return (
    <div className="flex h-screen flex-col bg-base">
      <div className="flex items-center gap-2 border-b border-line bg-surface px-4 py-2.5">
        <PegasusLogo size={20} />
        <span className="text-sm font-semibold text-fg">PegasusAI Chat</span>
      </div>
      <div className="flex-1 overflow-hidden">
        <ChatPanel />
      </div>
      <ChatInput />
    </div>
  );
}
