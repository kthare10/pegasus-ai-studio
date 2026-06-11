/**
 * PegasusAI mark: a stylized wing on a teal-to-navy badge. Used as the chat
 * logo / assistant avatar wherever a brand mark is needed.
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
        <linearGradient id="pegasus-badge" x1="0" y1="24" x2="24" y2="0">
          <stop offset="0%" stopColor="#1e3a5f" />
          <stop offset="100%" stopColor="#0891b2" />
        </linearGradient>
      </defs>
      <circle cx="12" cy="12" r="12" fill="url(#pegasus-badge)" />
      {/* wing: three swept feathers */}
      <path
        d="M5 15.5c4.5-1 7-3.5 9.5-8"
        stroke="#ffffff"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M7 18c4.5-1.2 7.5-4 9.5-8.5"
        stroke="#a5f3fc"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M10.5 19.5c3.5-1 5.8-3 7.3-6.3"
        stroke="#67e8f9"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      {/* spark */}
      <path
        d="M17.2 5.2l.5 1.3 1.3.5-1.3.5-.5 1.3-.5-1.3-1.3-.5 1.3-.5z"
        fill="#ffffff"
      />
    </svg>
  );
}
