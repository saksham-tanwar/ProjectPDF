import { useState } from "react";

import { initials } from "../lib/format";

export function Avatar({ name, picture, size = 32 }: { name: string; picture?: string | null; size?: number }) {
  const [failed, setFailed] = useState(false);
  const style = { width: size, height: size, fontSize: Math.round(size * 0.4) };
  if (picture && !failed) {
    return (
      <img
        className="avatar"
        src={picture}
        alt=""
        style={style}
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <span className="avatar avatar-initials" style={style} aria-hidden>
      {initials(name)}
    </span>
  );
}
