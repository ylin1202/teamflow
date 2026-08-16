"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useOrgStore } from "@/store/useOrgStore";
import { ArrowLeft, Kanban, FileCode2 } from "lucide-react";
import KanbanBoard from "./components/KanbanBoard";
import MarkdownSpecs from "./components/MarkdownSpecs";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { currentOrg } = useOrgStore();
  const projectId = params.id as string;

  const [activeTab, setActiveTab] = useState<"kanban" | "docs">("kanban");
  const canDelete = currentOrg?.role === "OWNER" || currentOrg?.role === "ADMIN";

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/dashboard")}
            className="p-2 border rounded-lg hover:bg-gray-50 transition text-gray-600"
            title="Back to Dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Project Workspace</h1>
            <p className="text-xs font-mono text-gray-400 mt-0.5">UUID: {projectId}</p>
          </div>
        </div>

        <div className="flex bg-gray-100 p-1 rounded-xl w-fit">
          <button
            onClick={() => setActiveTab("kanban")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition ${
              activeTab === "kanban"
                ? "bg-white text-blue-600 shadow-sm"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            <Kanban className="w-4 h-4" /> Task Board
          </button>
          <button
            onClick={() => setActiveTab("docs")}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition ${
              activeTab === "docs"
                ? "bg-white text-blue-600 shadow-sm"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            <FileCode2 className="w-4 h-4" /> Markdown Specs
          </button>
        </div>
      </div>

      {activeTab === "kanban" ? (
        <KanbanBoard projectId={projectId} canDelete={canDelete} />
      ) : (
        <MarkdownSpecs projectId={projectId} canDelete={canDelete} />
      )}
    </div>
  );
}