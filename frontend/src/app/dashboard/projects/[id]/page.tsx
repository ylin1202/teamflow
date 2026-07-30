"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";
import {
  ArrowLeft,
  Plus,
  CheckCircle2,
  Clock,
  ListTodo,
  Trash2,
  FileText,
  Kanban,
  FileCode2,
  Edit2,
  X,
  Save,
  Eye,
} from "lucide-react";

// 動態引入 ReactMarkdown 避免 SSR / ESM 型別衝突
const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

interface Task {
  id: string;
  project: string;
  title: string;
  description: string;
  status: "todo" | "in_progress" | "done";
  created_at: string;
}

interface Document {
  id: string;
  project: string;
  title: string;
  content: string;
  updated_at: string;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { currentOrg } = useOrgStore();
  const projectId = params.id as string;

  // 只有 OWNER 或 ADMIN 才能看到並執行刪除 (MEMBER 會自動隱藏刪除按鈕)
  const canDelete = currentOrg?.role === "OWNER" || currentOrg?.role === "ADMIN";

  // Tab 狀態: 'kanban' 或 'docs'
  const [activeTab, setActiveTab] = useState<"kanban" | "docs">("kanban");

  // Kanban Tasks 狀態
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDesc, setTaskDesc] = useState("");
  const [isAddingTask, setIsAddingTask] = useState(false);
  const [isTaskLoading, setIsTaskLoading] = useState(false);
  const [descTab, setDescTab] = useState<"edit" | "preview">("edit");

  // Task 編輯 Modal 狀態
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [editTaskTitle, setEditTaskTitle] = useState("");
  const [editTaskDesc, setEditTaskDesc] = useState("");
  const [editTaskStatus, setEditTaskStatus] = useState<Task["status"]>("todo");
  const [editTaskDescTab, setEditTaskDescTab] = useState<"edit" | "preview">("edit");
  const [isUpdatingTask, setIsUpdatingTask] = useState(false);

  // Project Docs 狀態
  const [docs, setDocs] = useState<Document[]>([]);
  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const [isAddingDoc, setIsAddingDoc] = useState(false);
  const [isDocLoading, setIsDocLoading] = useState(false);
  const [addDocTab, setAddDocTab] = useState<"edit" | "preview">("edit");

  // Document 編輯狀態
  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editDocTitle, setEditDocTitle] = useState("");
  const [editDocContent, setEditDocContent] = useState("");
  const [isEditDocLoading, setIsEditDocLoading] = useState(false);
  const [editDocTab, setEditDocTab] = useState<"edit" | "preview">("edit");

  // 1. 抓取 Task 清單
  const fetchTasks = useCallback(async () => {
    if (!projectId || !currentOrg) return;
    try {
      const res = await api.get<Task[]>(`/api/tasks/?project_id=${projectId}`);
      setTasks(res.data);
    } catch (err) {
      console.error("無法取得 Task 列表", err);
    }
  }, [projectId, currentOrg]);

  // 2. 抓取 Docs 清單
  const fetchDocs = useCallback(async () => {
    if (!projectId || !currentOrg) return;
    try {
      const res = await api.get<Document[]>(`/api/documents/?project_id=${projectId}`);
      setDocs(res.data);
    } catch (err) {
      console.error("無法取得 Document 列表", err);
    }
  }, [projectId, currentOrg]);

  useEffect(() => {
    if (currentOrg && projectId) {
      fetchTasks();
      fetchDocs();
    }
  }, [currentOrg, projectId, fetchTasks, fetchDocs]);

  // 新增 Task
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskTitle.trim()) return;
    setIsTaskLoading(true);
    try {
      await api.post("/api/tasks/", {
        project: projectId,
        title: taskTitle,
        description: taskDesc,
        status: "todo",
      });
      setTaskTitle("");
      setTaskDesc("");
      setIsAddingTask(false);
      fetchTasks();
    } catch (err) {
      console.error("建立 Task 失敗", err);
    } finally {
      setIsTaskLoading(false);
    }
  };

  // 開啟 Task 編輯 Modal
  const handleStartEditTask = (task: Task) => {
    setEditingTask(task);
    setEditTaskTitle(task.title);
    setEditTaskDesc(task.description || "");
    setEditTaskStatus(task.status);
    setEditTaskDescTab("edit");
  };

  // 送出 Task 編輯
  const handleUpdateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTask || !editTaskTitle.trim()) return;
    setIsUpdatingTask(true);
    try {
      await api.patch(`/api/tasks/${editingTask.id}/`, {
        title: editTaskTitle,
        description: editTaskDesc,
        status: editTaskStatus,
      });
      setEditingTask(null);
      fetchTasks();
    } catch (err) {
      console.error("更新 Task 失敗", err);
      alert("更新 Task 失敗");
    } finally {
      setIsUpdatingTask(false);
    }
  };

  // 更新 Task 狀態 (按鈕快速切換)
  const handleUpdateTaskStatus = async (taskId: string, newStatus: Task["status"]) => {
    try {
      await api.patch(`/api/tasks/${taskId}/`, { status: newStatus });
      fetchTasks();
    } catch (err) {
      console.error("更新 Task 狀態失敗", err);
    }
  };

  // 刪除 Task
  const handleDeleteTask = async (taskId: string) => {
    if (!confirm("確定要刪除這張 Task 嗎？")) return;
    try {
      await api.delete(`/api/tasks/${taskId}/`);
      fetchTasks();
    } catch (err) {
      console.error("刪除 Task 失敗", err);
    }
  };

  // 新增 Doc
  const handleCreateDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docTitle.trim()) return;
    setIsDocLoading(true);
    try {
      await api.post("/api/documents/", {
        project: projectId,
        title: docTitle,
        content: docContent,
      });
      setDocTitle("");
      setDocContent("");
      setIsAddingDoc(false);
      setAddDocTab("edit");
      fetchDocs();
    } catch (err) {
      console.error("建立文件失敗", err);
    } finally {
      setIsDocLoading(false);
    }
  };

  // 開始編輯 Doc
  const handleStartEditDoc = (doc: Document) => {
    setEditingDocId(doc.id);
    setEditDocTitle(doc.title);
    setEditDocContent(doc.content);
    setEditDocTab("edit");
  };

  // 取消編輯 Doc
  const handleCancelEditDoc = () => {
    setEditingDocId(null);
    setEditDocTitle("");
    setEditDocContent("");
    setEditDocTab("edit");
  };

  // 送出編輯 Doc
  const handleUpdateDoc = async (e: React.FormEvent, docId: string) => {
    e.preventDefault();
    if (!editDocTitle.trim()) return;
    setIsEditDocLoading(true);
    try {
      await api.patch(`/api/documents/${docId}/`, {
        title: editDocTitle,
        content: editDocContent,
      });
      setEditingDocId(null);
      fetchDocs();
    } catch (err) {
      console.error("更新文件失敗", err);
    } finally {
      setIsEditDocLoading(false);
    }
  };

  // 刪除 Doc
  const handleDeleteDoc = async (docId: string) => {
    if (!confirm("確定要刪除這份 Spec 文件嗎？")) return;
    try {
      await api.delete(`/api/documents/${docId}/`);
      fetchDocs();
    } catch (err) {
      console.error("刪除文件失敗", err);
    }
  };

  // Task 卡片通用元件
  const renderTaskCard = (t: Task) => (
    <div key={t.id} className="bg-white p-4 rounded-lg border shadow-sm space-y-3 hover:border-blue-300 transition">
      <div className="flex justify-between items-start gap-2">
        <h4 className="font-semibold text-gray-800 text-sm">{t.title}</h4>
        <div className="flex items-center gap-1">
          {/* 編輯 Task 按鈕：所有人皆可編輯 */}
          <button
            onClick={() => handleStartEditTask(t)}
            className="text-gray-400 hover:text-blue-600 p-1 rounded hover:bg-gray-100 transition"
            title="Edit Task"
          >
            <Edit2 className="w-3.5 h-3.5" />
          </button>

          {/* 💡 刪除 Task 按鈕：僅 OWNER 與 ADMIN 顯示 */}
          {canDelete && (
            <button
              onClick={() => handleDeleteTask(t.id)}
              className="text-gray-300 hover:text-red-500 p-1 rounded hover:bg-gray-100 transition"
              title="Delete Task"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {t.description && (
        <div className="text-xs text-gray-600 prose prose-slate line-clamp-3 bg-gray-50 p-2 rounded">
          <ReactMarkdown>{t.description}</ReactMarkdown>
        </div>
      )}

      {/* 狀態切換 */}
      <div className="pt-2 border-t flex justify-between items-center text-xs">
        {t.status === "todo" && (
          <div className="ml-auto">
            <button onClick={() => handleUpdateTaskStatus(t.id, "in_progress")} className="text-blue-600 hover:text-blue-800 font-medium">
              Start →
            </button>
          </div>
        )}
        {t.status === "in_progress" && (
          <>
            <button onClick={() => handleUpdateTaskStatus(t.id, "todo")} className="text-gray-400 hover:text-gray-600">
              ← Back
            </button>
            <button onClick={() => handleUpdateTaskStatus(t.id, "done")} className="text-emerald-600 font-medium">
              Complete ✓
            </button>
          </>
        )}
        {t.status === "done" && (
          <div>
            <button onClick={() => handleUpdateTaskStatus(t.id, "in_progress")} className="text-blue-600 hover:text-blue-800">
              ← Reopen
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* 頂部 Header & 導覽 */}
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

        {/* Tab 切換按鈕 */}
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

      {/* ==================== TAB 1: KANBAN BOARD ==================== */}
      {activeTab === "kanban" && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-800">Task Management</h2>
            <button
              onClick={() => setIsAddingTask(!isAddingTask)}
              className="flex items-center gap-2 bg-blue-600 text-white px-3.5 py-1.5 rounded-lg hover:bg-blue-700 transition text-xs font-medium"
            >
              <Plus className="w-4 h-4" /> Add Task Card
            </button>
          </div>

          {/* 新增 Task 表單 */}
          {isAddingTask && (
            <form onSubmit={handleCreateTask} className="bg-white p-5 border rounded-xl shadow-sm space-y-4 max-w-2xl">
              <h3 className="font-semibold text-sm text-gray-800">Create New Task</h3>
              <input
                type="text"
                placeholder="Task Title (e.g. Implement Multi-tenant Middleware)"
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                className="w-full border rounded-lg p-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />

              <div className="border rounded-lg p-2 space-y-2">
                <div className="flex items-center justify-between border-b pb-2 text-xs">
                  <span className="font-medium text-gray-500 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" /> Description (Markdown)
                  </span>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => setDescTab("edit")}
                      className={`px-2 py-0.5 rounded ${descTab === "edit" ? "bg-gray-200 font-medium text-gray-800" : "text-gray-400"}`}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setDescTab("preview")}
                      className={`px-2 py-0.5 rounded ${descTab === "preview" ? "bg-gray-200 font-medium text-gray-800" : "text-gray-400"}`}
                    >
                      Preview
                    </button>
                  </div>
                </div>

                {descTab === "edit" ? (
                  <textarea
                    placeholder="Supports Markdown: **bold**, - list, `code`..."
                    value={taskDesc}
                    onChange={(e) => setTaskDesc(e.target.value)}
                    className="w-full border-none outline-none text-sm h-24 text-gray-800 resize-none p-1"
                  />
                ) : (
                  <div className="prose prose-sm h-24 overflow-y-auto p-1 text-gray-800 bg-gray-50 rounded">
                    {taskDesc ? <ReactMarkdown>{taskDesc}</ReactMarkdown> : <span className="text-gray-400 text-xs">Nothing to preview</span>}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setIsAddingTask(false)} className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg">
                  Cancel
                </button>
                <button type="submit" disabled={isTaskLoading} className="px-4 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">
                  {isTaskLoading ? "Adding..." : "Save Task"}
                </button>
              </div>
            </form>
          )}

          {/* Kanban 看板 3 欄 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* To Do */}
            <div className="bg-gray-50 p-4 rounded-xl space-y-3 border border-gray-200">
              <div className="flex items-center justify-between font-semibold text-gray-700 pb-2 border-b border-gray-200 text-sm">
                <span className="flex items-center gap-2"><ListTodo className="w-4 h-4 text-gray-500" /> To Do</span>
                <span className="bg-gray-200 text-gray-700 text-xs px-2 py-0.5 rounded-full">{tasks.filter((t) => t.status === "todo").length}</span>
              </div>
              <div className="space-y-3">
                {tasks.filter((t) => t.status === "todo").map(renderTaskCard)}
              </div>
            </div>

            {/* In Progress */}
            <div className="bg-blue-50/40 p-4 rounded-xl space-y-3 border border-blue-100">
              <div className="flex items-center justify-between font-semibold text-blue-900 pb-2 border-b border-blue-100 text-sm">
                <span className="flex items-center gap-2"><Clock className="w-4 h-4 text-blue-500" /> In Progress</span>
                <span className="bg-blue-200 text-blue-800 text-xs px-2 py-0.5 rounded-full">{tasks.filter((t) => t.status === "in_progress").length}</span>
              </div>
              <div className="space-y-3">
                {tasks.filter((t) => t.status === "in_progress").map(renderTaskCard)}
              </div>
            </div>

            {/* Done */}
            <div className="bg-emerald-50/40 p-4 rounded-xl space-y-3 border border-emerald-100">
              <div className="flex items-center justify-between font-semibold text-emerald-900 pb-2 border-b border-emerald-100 text-sm">
                <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Done</span>
                <span className="bg-emerald-200 text-emerald-800 text-xs px-2 py-0.5 rounded-full">{tasks.filter((t) => t.status === "done").length}</span>
              </div>
              <div className="space-y-3">
                {tasks.filter((t) => t.status === "done").map(renderTaskCard)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Task 編輯 Modal */}
      {editingTask && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-lg font-bold text-gray-800">Edit Task Card</h3>
              <button onClick={() => setEditingTask(null)} className="text-gray-400 hover:text-gray-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateTask} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Title</label>
                <input
                  type="text"
                  value={editTaskTitle}
                  onChange={(e) => setEditTaskTitle(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Status</label>
                <select
                  value={editTaskStatus}
                  onChange={(e) => setEditTaskStatus(e.target.value as Task["status"])}
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                >
                  <option value="todo">To Do</option>
                  <option value="in_progress">In Progress</option>
                  <option value="done">Done</option>
                </select>
              </div>

              {/* Task 描述 (支援 Markdown Edit / Preview) */}
              <div className="border rounded-lg p-2 space-y-2">
                <div className="flex items-center justify-between border-b pb-2 text-xs">
                  <span className="font-medium text-gray-500 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" /> Description (Markdown)
                  </span>
                  <div className="flex gap-1 bg-gray-100 p-0.5 rounded-lg">
                    <button
                      type="button"
                      onClick={() => setEditTaskDescTab("edit")}
                      className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition ${
                        editTaskDescTab === "edit" ? "bg-white font-semibold text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-800"
                      }`}
                    >
                      <Edit2 className="w-3 h-3" /> Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditTaskDescTab("preview")}
                      className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition ${
                        editTaskDescTab === "preview" ? "bg-white font-semibold text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-800"
                      }`}
                    >
                      <Eye className="w-3 h-3" /> Preview
                    </button>
                  </div>
                </div>

                {editTaskDescTab === "edit" ? (
                  <textarea
                    value={editTaskDesc}
                    onChange={(e) => setEditTaskDesc(e.target.value)}
                    className="w-full border-none outline-none text-sm text-gray-800 h-32 resize-none p-1 font-mono"
                    placeholder="Task details in Markdown..."
                  />
                ) : (
                  <div className="prose prose-slate max-w-none text-sm text-gray-800 h-32 overflow-y-auto p-2 bg-gray-50 rounded">
                    {editTaskDesc ? <ReactMarkdown>{editTaskDesc}</ReactMarkdown> : <span className="text-gray-400 text-xs italic">Nothing to preview</span>}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingTask(null)}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdatingTask}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition disabled:opacity-50"
                >
                  {isUpdatingTask ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==================== TAB 2: MARKDOWN SPECS / DOCS ==================== */}
      {activeTab === "docs" && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-800">Project Specs & Documents</h2>
            <button
              onClick={() => setIsAddingDoc(!isAddingDoc)}
              className="flex items-center gap-2 bg-blue-600 text-white px-3.5 py-1.5 rounded-lg hover:bg-blue-700 transition text-xs font-medium"
            >
              <Plus className="w-4 h-4" /> Create Spec Document
            </button>
          </div>

          {/* 新增 Document 表單 */}
          {isAddingDoc && (
            <form onSubmit={handleCreateDoc} className="bg-white p-5 border rounded-xl shadow-sm space-y-4">
              <h3 className="font-semibold text-sm text-gray-800">Create New Spec / Document</h3>
              <input
                type="text"
                placeholder="Document Title (e.g. System Architecture Specification)"
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                className="w-full border rounded-lg p-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />

              <div className="border rounded-lg p-2 space-y-2">
                <div className="flex items-center justify-between border-b pb-2 text-xs">
                  <span className="font-medium text-gray-500 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" /> Spec Content (Markdown)
                  </span>
                  <div className="flex gap-1 bg-gray-100 p-0.5 rounded-lg">
                    <button
                      type="button"
                      onClick={() => setAddDocTab("edit")}
                      className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition ${
                        addDocTab === "edit" ? "bg-white font-semibold text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-800"
                      }`}
                    >
                      <Edit2 className="w-3 h-3" /> Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setAddDocTab("preview")}
                      className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition ${
                        addDocTab === "preview" ? "bg-white font-semibold text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-800"
                      }`}
                    >
                      <Eye className="w-3 h-3" /> Preview
                    </button>
                  </div>
                </div>

                {addDocTab === "edit" ? (
                  <textarea
                    placeholder="Write Markdown content here... (Supports # Heading, **bold**, lists, code blocks)"
                    value={docContent}
                    onChange={(e) => setDocContent(e.target.value)}
                    className="w-full border-none outline-none text-sm font-mono text-gray-800 h-64 resize-none p-1"
                  />
                ) : (
                  <div className="prose prose-slate max-w-none text-sm text-gray-800 h-64 overflow-y-auto p-3 bg-gray-50/50 rounded-lg">
                    {docContent ? (
                      <ReactMarkdown>{docContent}</ReactMarkdown>
                    ) : (
                      <span className="text-gray-400 text-xs italic">Nothing to preview. Start typing in Edit tab.</span>
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddingDoc(false)}
                  className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isDocLoading}
                  className="px-4 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                >
                  {isDocLoading ? "Saving..." : "Save Document"}
                </button>
              </div>
            </form>
          )}

          {/* Document 清單 */}
          {docs.length === 0 ? (
            <div className="bg-white border rounded-xl p-8 text-center text-gray-400 text-sm">
              No spec documents written for this project yet.
            </div>
          ) : (
            <div className="space-y-6">
              {docs.map((doc) => (
                <div key={doc.id} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
                  {editingDocId === doc.id ? (
                    <form onSubmit={(e) => handleUpdateDoc(e, doc.id)} className="space-y-4">
                      <div className="flex items-center justify-between border-b pb-3">
                        <h3 className="font-bold text-gray-800 text-base">Edit Spec Document</h3>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={handleCancelEditDoc}
                            className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg transition"
                          >
                            <X className="w-3.5 h-3.5" /> Cancel
                          </button>
                          <button
                            type="submit"
                            disabled={isEditDocLoading}
                            className="flex items-center gap-1 px-4 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition disabled:opacity-50"
                          >
                            <Save className="w-3.5 h-3.5" /> {isEditDocLoading ? "Saving..." : "Save Changes"}
                          </button>
                        </div>
                      </div>

                      <input
                        type="text"
                        value={editDocTitle}
                        onChange={(e) => setEditDocTitle(e.target.value)}
                        className="w-full border rounded-lg p-2.5 text-sm font-semibold text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        required
                      />

                      <div className="border rounded-lg p-2 space-y-2">
                        <div className="flex items-center justify-between border-b pb-2 text-xs">
                          <span className="font-medium text-gray-500 flex items-center gap-1">
                            <FileText className="w-3.5 h-3.5" /> Edit Content
                          </span>
                          <div className="flex gap-1 bg-gray-100 p-0.5 rounded-lg">
                            <button
                              type="button"
                              onClick={() => setEditDocTab("edit")}
                              className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition ${
                                editDocTab === "edit" ? "bg-white font-semibold text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-800"
                              }`}
                            >
                              <Edit2 className="w-3 h-3" /> Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditDocTab("preview")}
                              className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition ${
                                editDocTab === "preview" ? "bg-white font-semibold text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-800"
                              }`}
                            >
                              <Eye className="w-3 h-3" /> Preview
                            </button>
                          </div>
                        </div>

                        {editDocTab === "edit" ? (
                          <textarea
                            value={editDocContent}
                            onChange={(e) => setEditDocContent(e.target.value)}
                            className="w-full border-none outline-none text-sm font-mono text-gray-800 h-64 resize-none p-1"
                          />
                        ) : (
                          <div className="prose prose-slate max-w-none text-sm text-gray-800 h-64 overflow-y-auto p-3 bg-gray-50/50 rounded-lg">
                            {editDocContent ? (
                              <ReactMarkdown>{editDocContent}</ReactMarkdown>
                            ) : (
                              <span className="text-gray-400 text-xs italic">Nothing to preview.</span>
                            )}
                          </div>
                        )}
                      </div>
                    </form>
                  ) : (
                    <>
                      <div className="border-b pb-3 flex justify-between items-center">
                        <div>
                          <h3 className="font-bold text-gray-800 text-lg">{doc.title}</h3>
                          <span className="text-[11px] font-mono text-gray-400">
                            Updated: {doc.updated_at ? new Date(doc.updated_at).toLocaleString() : doc.id}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleStartEditDoc(doc)}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 hover:text-blue-600 transition"
                          >
                            <Edit2 className="w-3.5 h-3.5" /> Edit
                          </button>

                          {/* 刪除 Document 按鈕：僅 OWNER 與 ADMIN 顯示 */}
                          {canDelete && (
                            <button
                              onClick={() => handleDeleteDoc(doc.id)}
                              className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
                              title="Delete Document"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="prose prose-slate max-w-none text-sm text-gray-800 bg-gray-50/50 p-4 rounded-lg border">
                        <ReactMarkdown>{doc.content || "*No content provided.*"}</ReactMarkdown>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}