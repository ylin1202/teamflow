import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import axios from "axios";
import { getSession } from "next-auth/react";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: string;
  is_owner: boolean;
}

interface OrgState {
  organizations: Organization[];
  currentOrg: Organization | null;
  isLoading: boolean;
  setCurrentOrg: (org: Organization) => void;
  fetchOrganizations: () => Promise<void>;
  clearOrgState: () => void;
}

// 💡 注意：不要在 create<OrgState>() 後面加雙括號，直接傳入 (set, get) 即可
export const useOrgStore = create<OrgState>()(
  persist(
    (set, get) => ({
      organizations: [],
      currentOrg: null,
      isLoading: false,

      setCurrentOrg: (org) => set({ currentOrg: org }),

      fetchOrganizations: async () => {
        set({ isLoading: true });
        try {
          const session = await getSession();
          const token = session?.user?.backendToken;

          const res = await axios.get<Organization[]>(
            `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/organizations/me/`,
            {
              headers: {
                Authorization: token ? `Token ${token}` : "",
              },
            }
          );
          const orgs = res.data;

          set({ organizations: orgs });

          const current = get().currentOrg;
          if (!current || !orgs.some((o) => o.id === current.id)) {
            set({ currentOrg: orgs.length > 0 ? orgs[0] : null });
          }
        } catch (error) {
          console.error("無法取得組織清單:", error);
        } finally {
          set({ isLoading: false });
        }
      },

      clearOrgState: () => set({ organizations: [], currentOrg: null }),
    }),
    {
      name: "saas-org-storage",
      storage: createJSONStorage(() => localStorage),
      // 💡 明確將 state 型別標註為 OrgState
      partialize: (state: OrgState) => ({ currentOrg: state.currentOrg }),
    }
  )
);