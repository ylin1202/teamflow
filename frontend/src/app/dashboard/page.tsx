"use client";

import { useState, useEffect, useCallback } from "react";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

export default function DashboardPage() {
  const { currentOrg } = useOrgStore();

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [projectDesc, setProjectDesc] = useState("");
  const [isFetching, setIsFetching] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const fetchProjects = useCallback(async () => {
    if (!currentOrg) return;
    setIsFetching(true);
    try {
      const res = await api.get<Project[]>("/api/projects/");
      setProjects(res.data);
    } catch (err) {
      console.error("無法取得專案列表", err);
    } finally {
      setIsFetching(false);
    }
  }, [currentOrg]);

  useEffect(() => {
    if (currentOrg) {
      fetchProjects();
    }
  }, [currentOrg, fetchProjects]);

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
      fetchProjects();
    } catch (err) {
      console.error("建立專案失敗", err);
    } finally {
      setIsCreating(false);
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
          <h2 className="text-sm font-semibold text-gray-700">Active Tenant Metadata</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 font-mono text-xs">
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <span className="text-gray-400 block mb-1">Org Name</span>
              <span className="font-semibold text-gray-800">{currentOrg.name}</span>
            </div>
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <span className="text-gray-400 block mb-1">Role</span>
              <span className="font-semibold text-blue-600">{currentOrg.role}</span>
            </div>
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100 col-span-2">
              <span className="text-gray-400 block mb-1">Tenant UUIDv7</span>
              <span className="font-semibold text-gray-700 truncate block">{currentOrg.id}</span>
            </div>
          </div>
        </div>
      )}

      {/* 專案區塊 */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-6">
        <h2 className="text-lg font-semibold text-gray-800 border-b pb-3">Projects</h2>

        <form onSubmit={handleCreateProject} className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="Project Name"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            className="flex-1 rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <input
            type="text"
            placeholder="Description (Optional)"
            value={projectDesc}
            onChange={(e) => setProjectDesc(e.target.value)}
            className="flex-1 rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={isCreating}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition disabled:opacity-50"
          >
            {isCreating ? "Creating..." : "Create Project"}
          </button>
        </form>

        <div className="pt-2">
          {isFetching ? (
            <p className="text-sm text-gray-500">Loading projects...</p>
          ) : projects.length === 0 ? (
            <p className="text-sm text-gray-400">No projects found for this workspace.</p>
          ) : (
            <div className="divide-y divide-gray-100 border rounded-lg overflow-hidden">
              {projects.map((project) => (
                <div key={project.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{project.name}</p>
                    {project.description && (
                      <p className="text-xs text-gray-500 mt-0.5">{project.description}</p>
                    )}
                  </div>
                  <span className="font-mono text-[11px] text-gray-400 bg-gray-100 px-2 py-1 rounded">
                    {project.id}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}