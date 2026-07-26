"use client";

import { useOrgStore } from "@/store/useOrgStore";

export default function OrgSwitcher() {
  const { organizations, currentOrg, setCurrentOrg } = useOrgStore();

  if (!currentOrg) return null;

  return (
    <div className="flex items-center space-x-2">
      <span className="text-xs text-gray-400 font-medium hidden sm:inline">Workspace:</span>
      <select
        value={currentOrg.id}
        onChange={(e) => {
          const selected = organizations.find((o) => o.id === e.target.value);
          if (selected) setCurrentOrg(selected);
        }}
        className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 transition cursor-pointer"
      >
        {organizations.map((org) => (
          <option key={org.id} value={org.id}>
            {org.name} ({org.role})
          </option>
        ))}
      </select>
    </div>
  );
}