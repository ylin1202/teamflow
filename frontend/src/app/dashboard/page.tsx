"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  // 從 Zustand 取出組織狀態
  const { organizations, currentOrg, setCurrentOrg, isLoading } = useOrgStore();

  // 專案相關 State
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [projectDesc, setProjectDesc] = useState("");
  const [isFetchingProjects, setIsFetchingProjects] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // 取得當前組織的專案列表
  const fetchProjects = useCallback(async () => {
    if (!currentOrg) return;
    setIsFetchingProjects(true);
    try {
      const res = await api.get<Project[]>("/api/projects/");
      setProjects(res.data);
    } catch (err) {
      console.error("無法取得專案列表", err);
    } finally {
      setIsFetchingProjects(false);
    }
  }, [currentOrg]);

  // 當切換 Working Space (currentOrg) 時，重新抓取專案
  useEffect(() => {
    if (currentOrg) {
      fetchProjects();
    }
  }, [currentOrg, fetchProjects]);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  // 建立新專案
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) return;

    setIsCreating(true);
    try {
      await api.post("/api/projects/", {
        name: projectName,
        description: projectDesc,
      });
      setProjectName("");
      setProjectDesc("");
      fetchProjects(); // 重新整理清單
    } catch (err) {
      console.error("建立專案失敗", err);
    } finally {
      setIsCreating(false);
    }
  };

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

        {/* 🧪 資料隔離測試：專案管理卡片 */}
        <div className="rounded-xl bg-white p-6 shadow-md border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 border-b pb-3">
            🚀 專案列表 (測試 Tenant 數據隔離)
          </h2>

          {/* 新增專案表單 */}
          <form onSubmit={handleCreateProject} className="mt-4 space-y-3">
            <div className="flex space-x-3">
              <input
                type="text"
                placeholder="專案名稱"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <input
                type="text"
                placeholder="專案描述（可填）"
                value={projectDesc}
                onChange={(e) => setProjectDesc(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="submit"
                disabled={isCreating}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition disabled:opacity-50"
              >
                {isCreating ? "建立中..." : "新增專案"}
              </button>
            </div>
          </form>

          {/* 專案列表 */}
          <div className="mt-6">
            {isFetchingProjects ? (
              <p className="text-sm text-gray-500">載入專案中...</p>
            ) : projects.length === 0 ? (
              <p className="text-sm text-gray-400">目前這個 Working Space 尚無任何專案，試著建立一個吧！</p>
            ) : (
              <div className="space-y-2">
                {projects.map((project) => (
                  <div
                    key={project.id}
                    className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 p-3"
                  >
                    <div>
                      <p className="text-sm font-semibold text-gray-800">{project.name}</p>
                      {project.description && (
                        <p className="text-xs text-gray-500">{project.description}</p>
                      )}
                    </div>
                    <span className="font-mono text-[10px] text-gray-400">
                      ID: {project.id}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}