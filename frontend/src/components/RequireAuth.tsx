import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { useMe } from "../api/queries";
import { FullPageError, FullPageSpinner } from "./Feedback";

export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();

  if (me.isPending) return <FullPageSpinner label="Loading your workspace" />;
  if (me.isError) return <FullPageError message={me.error.message} onRetry={() => me.refetch()} />;
  if (!me.data) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}
