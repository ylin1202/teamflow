import axios from "axios";
import { getSession } from "next-auth/react";
import { useOrgStore } from "../store/useOrgStore";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  async (config) => {
    // 1. 取得 NextAuth Session Token
    // 注意：在 Client-side 取得 session，儘可能減少不必要的 API blocking
    if (typeof window !== "undefined") {
      const session = await getSession();
      if (session?.user?.backendToken) {
        config.headers.Authorization = `Token ${session.user.backendToken}`;
      }
    }

    // 2. 動態從 Zustand 抓取當前選取的 Organization ID
    const currentOrg = useOrgStore.getState().currentOrg;
    if (currentOrg?.id) {
      config.headers["X-Organization-ID"] = currentOrg.id;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;