"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { usePanelStore } from "@/lib/stores/panel-store";

const NAV_ITEMS: {
  href: string;
  label: string;
  icon: string;
  external?: boolean;
}[] = [
  { href: "/workflows", label: "Workflows", icon: "📊" },
  { href: "/workbench", label: "Workbench", icon: "🔧" },
  // Notebooks is just a link to the always-on JupyterLab (opens in a new tab),
  // not an in-studio pane.
  { href: "/jupyter/lab", label: "Notebooks", icon: "📓", external: true },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export function Sidebar() {
  const pathname = usePathname();
  const chatOpen = usePanelStore((s) => s.chatOpen);
  const terminalOpen = usePanelStore((s) => s.terminalOpen);
  const toggleChat = usePanelStore((s) => s.toggleChat);
  const toggleTerminal = usePanelStore((s) => s.toggleTerminal);

  // Auth-gated deployments proxy /logout to the auth layer (vouch); plain
  // deployments have no such route and Next.js 404s — hide Sign out there.
  const [canSignOut, setCanSignOut] = useState(false);
  useEffect(() => {
    fetch("/logout", { method: "HEAD", redirect: "manual" })
      .then((r) => setCanSignOut(r.status !== 404))
      .catch(() => setCanSignOut(false));
  }, []);

  return (
    <aside className="flex w-56 flex-col border-r border-gray-200 bg-white">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-gray-200 px-4">
        <span className="text-lg font-bold text-pegasus-700">PegasusAI</span>
        <span className="text-xs text-gray-400">Studio</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-3">
        {NAV_ITEMS.map((item) => {
          const classes =
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors text-gray-600 hover:bg-gray-100 hover:text-gray-900";

          // External links (e.g. JupyterLab) open in a new browser tab.
          if (item.external) {
            return (
              <a
                key={item.href}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                className={classes}
              >
                <span>{item.icon}</span>
                {item.label}
                <span className="ml-auto text-xs text-gray-400">↗</span>
              </a>
            );
          }

          const active =
            pathname === item.href || pathname?.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-pegasus-50 text-pegasus-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}

        {/* Quick Access */}
        <div className="mt-4 border-t border-gray-200 pt-3">
          <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wider text-gray-400">
            Quick Access
          </p>
          <button
            onClick={toggleChat}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              chatOpen
                ? "bg-pegasus-50 text-pegasus-700"
                : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            )}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            PegasusAI Chat
          </button>
          <button
            onClick={toggleTerminal}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              terminalOpen
                ? "bg-gray-800 text-white"
                : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            )}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="4 17 10 11 4 5" />
              <line x1="12" y1="19" x2="20" y2="19" />
            </svg>
            Terminal
          </button>
        </div>
      </nav>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-gray-200 p-3 text-xs text-gray-400">
        <span>v0.1.0</span>
        {canSignOut && (
          <a
            href="/logout"
            onClick={(e) => {
              e.preventDefault();
              // Land on the public welcome page after the session is cleared
              window.location.href = `/logout?url=${window.location.origin}/welcome`;
            }}
            className="rounded px-2 py-1 font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
          >
            Sign out
          </a>
        )}
      </div>
    </aside>
  );
}
