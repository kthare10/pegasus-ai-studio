"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useThemeStore, applyTheme, type Theme } from "@/lib/stores/theme-store";

/**
 * Top-right user menu (LoomAI-style): the authenticated identity with a
 * dropdown for theme, Settings, Help, and Sign out.
 *
 * Identity comes from /api/whoami (the gateway's X-Auth-User header — CILogon
 * email or basic-auth username). With no identity (plain container) the menu
 * still renders for theme/Settings/Help, just without the email chrome. Sign
 * out shows only when an auth layer answers on /logout.
 */
const THEMES: { value: Theme; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "☀️" },
  { value: "dark", label: "Dark", icon: "🌙" },
  { value: "system", label: "System", icon: "🖥️" },
];

export function UserMenu() {
  const [email, setEmail] = useState<string | null>(null);
  const [canSignOut, setCanSignOut] = useState(false);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);

  // Re-assert the persisted theme after hydration (system changes, SSR mismatch).
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    fetch("/api/whoami")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setEmail(d?.email ?? null))
      .catch(() => setEmail(null));
    fetch("/logout", { method: "HEAD", redirect: "manual" })
      .then((r) => setCanSignOut(r.status !== 404))
      .catch(() => setCanSignOut(false));
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, [open]);

  const initial = email ? email[0]?.toUpperCase() ?? "?" : "⚙";

  return (
    <div className="fixed right-4 top-2.5 z-50 flex items-center gap-3">
      <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1 pr-3 text-sm shadow-sm transition-colors hover:bg-muted"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-fg">
          {initial}
        </span>
        {email && (
          <span className="max-w-[180px] truncate text-fgmuted">{email}</span>
        )}
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-fgsubtle"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-60 overflow-hidden rounded-lg border border-line bg-surface shadow-lg">
          {email && (
            <div className="border-b border-line px-4 py-3">
              <p className="text-xs text-fgsubtle">Signed in as</p>
              <p className="truncate text-sm font-medium text-fg">{email}</p>
            </div>
          )}

          {/* Theme switch */}
          <div className="border-b border-line px-4 py-3">
            <p className="mb-2 text-xs text-fgsubtle">Theme</p>
            <div className="flex gap-1 rounded-md bg-muted p-1">
              {THEMES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTheme(t.value)}
                  className={
                    "flex flex-1 items-center justify-center gap-1 rounded px-2 py-1 text-xs transition-colors " +
                    (theme === t.value
                      ? "bg-surface text-fg shadow-sm"
                      : "text-fgmuted hover:text-fg")
                  }
                  title={t.label}
                >
                  <span>{t.icon}</span>
                  <span className="hidden sm:inline">{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          <nav className="py-1 text-sm text-fg">
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="block px-4 py-2 hover:bg-muted"
            >
              ⚙️ Settings
            </Link>
            <a
              href="https://github.com/kthare10/pegasus-ai-studio#readme"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setOpen(false)}
              className="block px-4 py-2 hover:bg-muted"
            >
              ❓ Help
            </a>
            {canSignOut && (
              <a
                href="/logout"
                onClick={(e) => {
                  e.preventDefault();
                  window.location.href = `/logout?url=${window.location.origin}/welcome`;
                }}
                className="block border-t border-line px-4 py-2 text-rose-500 hover:bg-muted"
              >
                ↩ Sign out
              </a>
            )}
          </nav>
        </div>
      )}
      </div>
    </div>
  );
}
