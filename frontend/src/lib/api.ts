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
    const session = await getSession();

    if (session?.user?.backendToken) {
      config.headers.Authorization = `Token ${session.user.backendToken}`;
    }

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