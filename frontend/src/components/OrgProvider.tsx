"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useOrgStore } from "@/store/useOrgStore";

export default function OrgProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const fetchOrganizations = useOrgStore((state) => state.fetchOrganizations);
  const clearOrgState = useOrgStore((state) => state.clearOrgState);

  useEffect(() => {
    if (status === "authenticated") {
      fetchOrganizations();
    } else if (status === "unauthenticated") {
      clearOrgState();
    }
  }, [status, fetchOrganizations, clearOrgState]);

  return <>{children}</>;
}