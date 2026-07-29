import { create } from "zustand";
import { persist } from "zustand/middleware";
import api from "@/lib/api"; 

export interface Organization {
  id: string;
  name: string;
  slug?: string;
  role?: string;
}

// 1. 在介面宣告 fetchOrganizations 與 clearOrgState
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

      // 2. 實現抓取 Organizations 的邏輯
      fetchOrganizations: async () => {
        try {
          // 修正這裡：加上 /me/ 匹配後端 urls.py
          const res = await api.get<Organization[]>("/api/organizations/me/");
          const orgs = res.data;
          set({ organizations: orgs });

          // 關鍵：如果沒有 currentOrg，或是目前的 currentOrg 不在清單中，自動設為第一個 Org
          const current = get().currentOrg;
          if (orgs && orgs.length > 0) {
            const exists = orgs.some((o) => o.id === current?.id);
            if (!current || !exists) {
              set({ currentOrg: orgs[0] });
            }
          }
        } catch (err) {
          console.error("Failed to fetch organizations:", err);
        }
      },

      // 3. 實現登出時清空 State
      clearOrgState: () => {
        set({ currentOrg: null, organizations: [] });
      },
    }),
    {
      name: "saas-org-storage", // localStorage 的 key
    }
  )
);