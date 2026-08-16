"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

interface OrgProjectUsage {
  plan: string;
  current_projects: number;
  max_projects: number;
}

export default function DashboardPage() {
  const router = useRouter();
  const { currentOrg } = useOrgStore();

  const [projects, setProjects] = useState<Project[]>([]);
  const [usage, setUsage] = useState<OrgProjectUsage | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectDesc, setProjectDesc] = useState("");
  const [isFetching, setIsFetching] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // 編輯 Modal 相關 State
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);

  // 只有 OWNER 或 ADMIN 才能刪除專案 (MEMBER 不能刪除)
  const canDelete = currentOrg?.role === "OWNER" || currentOrg?.role === "ADMIN";

  // 同時獲取專案清單與用量配額 API
  const fetchData = useCallback(async () => {
    if (!currentOrg) return;
    setIsFetching(true);
    try {
      const [projectsRes, usageRes] = await Promise.all([
        api.get<Project[]>("/api/projects/"),
        api.get<OrgProjectUsage>("/api/billing/project-usage/", {
          headers: { "X-Organization-ID": currentOrg.id },
        }).catch(() => null), // 降級處理
      ]);

      setProjects(projectsRes.data);
      if (usageRes) setUsage(usageRes.data);
    } catch (err) {
      console.error("無法取得 Dashboard 資料", err);
    } finally {
      setIsFetching(false);
    }
  }, [currentOrg]);

  useEffect(() => {
    if (currentOrg) {
      fetchData();
    }
  }, [currentOrg, fetchData]);

  // 判斷專案是否已達上限
  const isLimitReached = usage ? usage.current_projects >= usage.max_projects : false;

  // 建立專案
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim() || isLimitReached) return;

    setIsCreating(true);
    try {
      await api.post("/api/projects/", {
        name: projectName,
        description: projectDesc,
      });
      setProjectName("");
      setProjectDesc("");
      fetchData();
    } catch (err: any) {
      console.error("建立專案失敗", err);
      const msg = err.response?.data?.detail || "建立專案失敗";
      alert(msg);
    } finally {
      setIsCreating(false);
    }
  };

  // 開啟編輯 Modal
  const handleOpenEdit = (project: Project, e: React.MouseEvent) => {
    e.stopPropagation(); // 阻止觸發卡片跳轉
    setEditingProject(project);
    setEditName(project.name);
    setEditDesc(project.description || "");
  };

  // 送出編輯
  const handleUpdateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProject || !editName.trim()) return;

    setIsUpdating(true);
    try {
      await api.patch(`/api/projects/${editingProject.id}/`, {
        name: editName,
        description: editDesc,
      });
      setEditingProject(null);
      fetchData();
    } catch (err) {
      console.error("更新專案失敗", err);
      alert("更新專案失敗");
    } finally {
      setIsUpdating(false);
    }
  };

  // 刪除專案 (僅 OWNER / ADMIN 可執行)
  const handleDeleteProject = async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // 阻止觸發卡片跳轉
    if (!window.confirm("確定要刪除此專案嗎？相關資料將無法復原。")) return;

    try {
      await api.delete(`/api/projects/${projectId}/`);
      fetchData();
    } catch (err: any) {
      console.error("刪除專案失敗", err);
      const msg = err.response?.data?.detail || "刪除專案失敗，僅 Admin/Owner 可刪除專案。";
      alert(msg);
    }
  };

  return (
    <div className="space-y-6">
      {/* 頁面標題 */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500">
          Overview of your active workspace resources and projects.
        </p>
      </div>

      {/* 租戶詳細資訊小卡 */}
      {currentOrg && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-2">
          <h2 className="text-sm font-semibold text-gray-700">Current Workspace</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 font-mono text-xs">
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <span className="text-gray-400 block mb-1">Workspace Name</span>
              <span className="font-semibold text-gray-800">{currentOrg.name}</span>
            </div>
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <span className="text-gray-400 block mb-1">Your Role</span>
              <span className="font-semibold text-blue-600">{currentOrg.role}</span>
            </div>
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100 col-span-2">
              <span className="text-gray-400 block mb-1">Workspace ID</span>
              <span className="font-semibold text-gray-700 truncate block">{currentOrg.id}</span>
            </div>
          </div>
        </div>
      )}

      {isLimitReached && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-800">
          <div className="text-xs">
            <p className="font-bold text-sm">
              Project Limit Reached ({usage?.current_projects}/{usage?.max_projects})
            </p>
            <p className="mt-0.5 text-amber-700">
              Your current plan ({usage?.plan}) allows up to {usage?.max_projects} projects. Please upgrade your plan in Billing to create more projects.
            </p>
          </div>
          {currentOrg?.role === "OWNER" && (
            <Link
              href="/dashboard/billing"
              className="bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs px-3.5 py-2 rounded-lg transition shrink-0 text-center"
            >
              Upgrade Plan
            </Link>
          )}
        </div>
      )}

      {/* 專案區塊 */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-6">
        <div className="flex justify-between items-center border-b pb-3">
          <h2 className="text-lg font-semibold text-gray-800">Projects</h2>
          {usage && (
            <span className="text-xs font-mono text-gray-400">
              Quota: {usage.current_projects} / {usage.max_projects}
            </span>
          )}
        </div>

        <form onSubmit={handleCreateProject} className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="Project Name"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            disabled={isLimitReached}
            className="flex-1 rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 disabled:bg-gray-100 disabled:cursor-not-allowed"
            required
          />
          <input
            type="text"
            placeholder="Description (Optional)"
            value={projectDesc}
            onChange={(e) => setProjectDesc(e.target.value)}
            disabled={isLimitReached}
            className="flex-1 rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={isCreating || isLimitReached}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCreating ? "Creating..." : isLimitReached ? "Quota Reached" : "Create Project"}
          </button>
        </form>

        <div className="pt-2">
          {isFetching ? (
            <p className="text-sm text-gray-500">Loading projects...</p>
          ) : projects.length === 0 ? (
            <p className="text-sm text-gray-400">No projects found for this workspace.</p>
          ) : (
            <div className="divide-y divide-gray-100 border rounded-lg overflow-hidden bg-white shadow-sm">
              {projects.map((project) => (
                <div
                  key={project.id}
                  onClick={() => router.push(`/dashboard/projects/${project.id}`)}
                  className="p-4 flex items-center justify-between hover:bg-blue-50/50 cursor-pointer transition group"
                >
                  <div className="flex-1 pr-4">
                    <p className="text-sm font-semibold text-gray-800 group-hover:text-blue-600 transition">
                      {project.name}
                    </p>
                    {project.description && (
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                        {project.description}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[11px] text-gray-500 bg-gray-50 px-2 py-1 rounded border border-gray-200 hidden sm:inline-block">
                      <span className="text-gray-400 mr-1 font-sans font-medium">Project ID:</span>
                      {project.id}
                    </span>

                    {/* 編輯按鈕 (所有角色皆可編輯) */}
                    <button
                      onClick={(e) => handleOpenEdit(project, e)}
                      className="text-xs font-medium text-gray-600 hover:text-blue-600 px-2 py-1 rounded hover:bg-gray-100 transition"
                    >
                      Edit
                    </button>

                    {/* 刪除按鈕 (僅 Admin / Owner 可見) */}
                    {canDelete && (
                      <button
                        onClick={(e) => handleDeleteProject(project.id, e)}
                        className="text-xs font-medium text-red-600 hover:text-red-800 px-2 py-1 rounded hover:bg-red-50 transition"
                      >
                        Delete
                      </button>
                    )}

                    <span className="text-gray-400 group-hover:translate-x-1 group-hover:text-blue-600 transition text-sm ml-1">
                      →
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 編輯專案 Modal */}
      {editingProject && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-gray-800">Edit Project</h3>
            <form onSubmit={handleUpdateProject} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">
                  Project Name
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">
                  Description
                </label>
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none text-gray-900"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingProject(null)}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdating}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition disabled:opacity-50"
                >
                  {isUpdating ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}