import { create } from "zustand";
import { persist } from "zustand/middleware";
import api from "@/lib/api"; 

export interface Organization {
  id: string;
  name: string;
  slug?: string;
  role?: string;
  plan?: string; // Plan tier field (e.g., 'FREE', 'PRO', 'ENTERPRISE')
}

// Declare fetchOrganizations and clearOrgState in state interface
interface OrgState {
  currentOrg: Organization | null;
  organizations: Organization[];
  setCurrentOrg: (org: Organization) => void;
  setOrganizations: (orgs: Organization[]) => void;
  fetchOrganizations: () => Promise<void>; 
  clearOrgState: () => void;              
}

export const useOrgStore = create<OrgState>()(
  persist(
    (set, get) => ({
      currentOrg: null,
      organizations: [],

      setCurrentOrg: (org) => set({ currentOrg: org }),

      setOrganizations: (orgs) => set({ organizations: orgs }),

      // Implement organization fetching logic
      fetchOrganizations: async () => {
        try {
          const res = await api.get<Organization[]>("/api/organizations/me/");
          const orgs = res.data;
          set({ organizations: orgs });

          // If no currentOrg is set, or if it is not present in the fetched list, default to the first organization
          const current = get().currentOrg;
          if (orgs && orgs.length > 0) {
            const exists = orgs.some((o) => o.id === current?.id);
            if (!current || !exists) {
              set({ currentOrg: orgs[0] });
            } else {
              // If currentOrg already exists, sync it with the latest organization data (e.g., updated plan)
              const updatedCurrent = orgs.find((o) => o.id === current.id);
              if (updatedCurrent) {
                set({ currentOrg: updatedCurrent });
              }
            }
          }
        } catch (err) {
          console.error("Failed to fetch organizations:", err);
        }
      },

      // Reset state upon sign-out
      clearOrgState: () => {
        set({ currentOrg: null, organizations: [] });
      },
    }),
    {
      name: "saas-org-storage", // localStorage key
    }
  )
);