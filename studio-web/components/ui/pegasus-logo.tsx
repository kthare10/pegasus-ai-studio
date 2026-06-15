/**
 * PegasusAI mark: three swept wing feathers rising to an AI sparkle, on a
 * teal-to-navy badge. Used as the chat logo / assistant avatar. Tuned to read
 * cleanly from ~16px (sidebar/avatar) up.
 */
export function PegasusLogo({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="pegasus-badge" x1="2" y1="22" x2="22" y2="2">
          <stop offset="0%" stopColor="#0f2942" />
          <stop offset="55%" stopColor="#1e3a5f" />
          <stop offset="100%" stopColor="#0891b2" />
        </linearGradient>
      </defs>

      <circle cx="12" cy="12" r="12" fill="url(#pegasus-badge)" />

      {/* Wing: three feathers fanning up-right from a short leading edge,
          brightening toward the tip for depth. */}
      <path
        d="M5.4 17 Q11 13.6 16.6 11.1"
        stroke="#ffffff"
        strokeWidth="1.7"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M6 15.9 Q10.6 11.5 15.1 7.7"
        stroke="#cdeffb"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M6.7 14.9 Q9.7 10.6 12.8 6.4"
        stroke="#7fe3f5"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
      />

      {/* AI sparkle in the open upper-right */}
      <path
        d="M17.9 3.7 C18.15 5.45 18.75 6.05 20.5 6.3 C18.75 6.55 18.15 7.15 17.9 8.9 C17.65 7.15 17.05 6.55 15.3 6.3 C17.05 6.05 17.65 5.45 17.9 3.7 Z"
        fill="#ffffff"
      />
    </svg>
  );
}
