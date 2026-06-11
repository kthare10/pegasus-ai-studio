"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { usePanelStore } from "@/lib/stores/panel-store";
import { PegasusLogo } from "@/components/ui/pegasus-logo";

// Settings is intentionally not here — it lives in the top-right user menu.
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
];

export function Sidebar() {
  const pathname = usePathname();
  const chatOpen = usePanelStore((s) => s.chatOpen);
  const terminalOpen = usePanelStore((s) => s.terminalOpen);
  const collapsed = usePanelStore((s) => s.sidebarCollapsed);
  const toggleChat = usePanelStore((s) => s.toggleChat);
  const toggleTerminal = usePanelStore((s) => s.toggleTerminal);
  const toggleSidebar = usePanelStore((s) => s.toggleSidebar);

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-gray-200 bg-white transition-[width] duration-150",
        collapsed ? "w-14" : "w-56"
      )}
    >
      {/* Logo + collapse toggle */}
      <div
        className={cn(
          "flex h-14 items-center border-b border-gray-200",
          collapsed ? "justify-center px-0" : "justify-between px-4"
        )}
      >
        {!collapsed && (
          <span className="flex items-baseline gap-1.5">
            <span className="text-lg font-bold text-pegasus-700">
              PegasusAI
            </span>
            <span className="text-xs text-gray-400">Studio</span>
          </span>
        )}
        <button
          onClick={toggleSidebar}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
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
            className={cn("transition-transform", collapsed && "rotate-180")}
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
        {NAV_ITEMS.map((item) => {
          const base = cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            collapsed && "justify-center px-0"
          );

          // External links (e.g. JupyterLab) open in a new browser tab.
          if (item.external) {
            return (
              <a
                key={item.href}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                title={item.label}
                className={cn(
                  base,
                  "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <span>{item.icon}</span>
                {!collapsed && (
                  <>
                    {item.label}
                    <span className="ml-auto text-xs text-gray-400">↗</span>
                  </>
                )}
              </a>
            );
          }

          const active =
            pathname === item.href || pathname?.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              className={cn(
                base,
                active
                  ? "bg-pegasus-50 text-pegasus-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )}
            >
              <span>{item.icon}</span>
              {!collapsed && item.label}
            </Link>
          );
        })}

        {/* Quick Access */}
        <div className="mt-4 border-t border-gray-200 pt-3">
          {!collapsed && (
            <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wider text-gray-400">
              Quick Access
            </p>
          )}
          <button
            onClick={toggleChat}
            title="PegasusAI Chat"
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              collapsed && "justify-center px-0",
              chatOpen
                ? "bg-pegasus-50 text-pegasus-700"
                : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            )}
          >
            <PegasusLogo size={18} />
            {!collapsed && "PegasusAI Chat"}
          </button>
          <button
            onClick={toggleTerminal}
            title="Terminal"
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              collapsed && "justify-center px-0",
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
            {!collapsed && "Terminal"}
          </button>
        </div>
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="border-t border-gray-200 p-3 text-xs text-gray-400">
          v0.1.0
        </div>
      )}
    </aside>
  );
}
