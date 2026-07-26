"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useOrgStore } from "@/store/useOrgStore";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  // 從 Zustand 取出組織狀態
  const { organizations, currentOrg, setCurrentOrg, isLoading } = useOrgStore();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  if (status === "loading" || isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500 font-medium">載入系統狀態中...</p>
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Header 卡片 */}
        <div className="flex items-center justify-between rounded-xl bg-white p-6 shadow-md">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">SaaS 控制台</h1>
            <p className="text-sm text-gray-500">{session.user?.email}</p>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="rounded-md bg-red-500 px-4 py-2 text-sm text-white hover:bg-red-600 transition"
          >
            登出
          </button>
        </div>

        {/* 多租戶 Organization Switcher 卡片 */}
        <div className="rounded-xl bg-white p-6 shadow-md border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 border-b pb-3">
            🏢 當前選擇的 Working Space (Tenant)
          </h2>

          <div className="mt-4 flex items-center space-x-4">
            <label className="text-sm font-medium text-gray-700">切換組織：</label>
            <select
              value={currentOrg?.id || ""}
              onChange={(e) => {
                const selected = organizations.find((o) => o.id === e.target.value);
                if (selected) setCurrentOrg(selected);
              }}
              className="rounded-lg border border-gray-300 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name} ({org.role})
                </option>
              ))}
            </select>
          </div>

          {currentOrg && (
            <div className="mt-6 rounded-lg bg-gray-50 p-4 font-mono text-xs text-gray-700 space-y-1 border border-gray-200">
              <p><span className="font-bold text-blue-600">Org ID (UUIDv7):</span> {currentOrg.id}</p>
              <p><span className="font-bold text-blue-600">Org Slug:</span> {currentOrg.slug}</p>
              <p><span className="font-bold text-blue-600">Role:</span> {currentOrg.role}</p>
              <p><span className="font-bold text-blue-600">Is Owner:</span> {currentOrg.is_owner ? "Yes" : "No"}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}