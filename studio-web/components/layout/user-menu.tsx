"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

/**
 * Top-right user menu (LoomAI-style): the authenticated identity with a
 * dropdown for Settings, Help, and Sign out.
 *
 * Identity comes from /api/whoami (the gateway's X-Auth-User header — CILogon
 * email or basic-auth username). In the plain single-user container there is
 * no identity, so the menu hides itself entirely. Sign out shows only when an
 * auth layer answers on /logout.
 */
export function UserMenu() {
  const [email, setEmail] = useState<string | null>(null);
  const [canSignOut, setCanSignOut] = useState(false);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

  // With no identity (plain single-user deployments) the menu still renders —
  // Settings/Help moved here from the sidebar — just without the email chrome.
  const initial = email ? email[0]?.toUpperCase() ?? "?" : "⚙";

  return (
    <div ref={menuRef} className="fixed right-4 top-2.5 z-50">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-gray-200 bg-white py-1 pl-1 pr-3 text-sm shadow-sm transition-colors hover:bg-gray-50"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-pegasus-600 text-xs font-semibold text-white">
          {initial}
        </span>
        {email && (
          <span className="max-w-[180px] truncate text-gray-700">{email}</span>
        )}
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-gray-400"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-56 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
          {email && (
            <div className="border-b border-gray-100 px-4 py-3">
              <p className="text-xs text-gray-400">Signed in as</p>
              <p className="truncate text-sm font-medium text-gray-800">
                {email}
              </p>
            </div>
          )}
          <nav className="py-1 text-sm text-gray-700">
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="block px-4 py-2 hover:bg-gray-50"
            >
              ⚙️ Settings
            </Link>
            <a
              href="https://github.com/kthare10/pegasus-ai-studio#readme"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setOpen(false)}
              className="block px-4 py-2 hover:bg-gray-50"
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
                className="block border-t border-gray-100 px-4 py-2 text-red-600 hover:bg-red-50"
              >
                ↩ Sign out
              </a>
            )}
          </nav>
        </div>
      )}
    </div>
  );
}
