"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Plus, CheckCircle2, Clock, ListTodo, Trash2, FileText, Edit2, X, Eye } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";

export interface Task {
  id: string;
  project: string;
  title: string;
  description: string;
  status: "todo" | "in_progress" | "done";
  created_at: string;
}

interface KanbanBoardProps {
  projectId: string;
  canDelete: boolean;
}

export default function KanbanBoard({ projectId, canDelete }: KanbanBoardProps) {
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

  const fetchTasks = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await api.get<Task[]>(`/api/tasks/?project_id=${projectId}`);
      setTasks(res.data);
    } catch (err) {
      console.error("Failed to fetch task list", err);
    }
  }, [projectId]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

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
      console.error("Failed to create task", err);
    } finally {
      setIsTaskLoading(false);
    }
  };

  const handleStartEditTask = (task: Task) => {
    setEditingTask(task);
    setEditTaskTitle(task.title);
    setEditTaskDesc(task.description || "");
    setEditTaskStatus(task.status);
    setEditTaskDescTab("edit");
  };

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
      console.error("Failed to update task", err);
      alert("Failed to update task");
    } finally {
      setIsUpdatingTask(false);
    }
  };

  const handleUpdateTaskStatus = async (taskId: string, newStatus: Task["status"]) => {
    try {
      await api.patch(`/api/tasks/${taskId}/`, { status: newStatus });
      fetchTasks();
    } catch (err) {
      console.error("Failed to update task status", err);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!confirm("Are you sure you want to delete this task?")) return;
    try {
      await api.delete(`/api/tasks/${taskId}/`);
      fetchTasks();
    } catch (err) {
      console.error("Failed to delete task", err);
    }
  };

  const renderTaskCard = (t: Task) => (
    <div
      key={t.id}
      className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm space-y-2.5 hover:border-blue-300 transition"
    >
      <div className="flex justify-between items-start gap-2">
        <h4 className="font-semibold text-gray-800 text-sm leading-snug">{t.title}</h4>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => handleStartEditTask(t)}
            className="text-gray-400 hover:text-blue-600 p-1 rounded-lg hover:bg-gray-100 transition"
            title="Edit Task"
          >
            <Edit2 className="w-3.5 h-3.5" />
          </button>
          {canDelete && (
            <button
              onClick={() => handleDeleteTask(t.id)}
              className="text-gray-300 hover:text-red-500 p-1 rounded-lg hover:bg-red-50 transition"
              title="Delete Task"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {t.description && (
        <div className="text-xs text-gray-700 bg-gray-50/80 p-2.5 rounded-lg border border-gray-100 max-h-56 overflow-y-auto">
          <MarkdownRenderer content={t.description} />
        </div>
      )}

      <div className="pt-1.5 border-t border-gray-100 flex justify-between items-center text-xs">
        {t.status === "todo" && (
          <div className="ml-auto">
            <button
              onClick={() => handleUpdateTaskStatus(t.id, "in_progress")}
              className="text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1 hover:underline cursor-pointer"
            >
              Start →
            </button>
          </div>
        )}
        {t.status === "in_progress" && (
          <>
            <button
              onClick={() => handleUpdateTaskStatus(t.id, "todo")}
              className="text-gray-400 hover:text-gray-600 font-medium cursor-pointer"
            >
              ← Back
            </button>
            <button
              onClick={() => handleUpdateTaskStatus(t.id, "done")}
              className="text-emerald-600 hover:text-emerald-700 font-semibold flex items-center gap-1 hover:underline cursor-pointer"
            >
              Complete ✓
            </button>
          </>
        )}
        {t.status === "done" && (
          <div>
            <button
              onClick={() => handleUpdateTaskStatus(t.id, "in_progress")}
              className="text-blue-600 hover:text-blue-700 font-medium hover:underline cursor-pointer"
            >
              ← Reopen
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
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

      {isAddingTask && (
        <form onSubmit={handleCreateTask} className="bg-white p-5 border border-gray-200 rounded-xl shadow-sm space-y-4 max-w-2xl">
          <h3 className="font-semibold text-sm text-gray-800">Create New Task</h3>
          <input
            type="text"
            placeholder="Task Title (e.g. Implement Multi-tenant Middleware)"
            value={taskTitle}
            onChange={(e) => setTaskTitle(e.target.value)}
            className="w-full border rounded-lg p-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />

          <div className="border border-gray-200 rounded-lg p-2 space-y-2">
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
                className="w-full border-none outline-none text-sm h-28 text-gray-800 resize-none p-1"
              />
            ) : (
              <div className="h-28 overflow-y-auto p-2 text-gray-800 bg-gray-50 rounded">
                {taskDesc ? (
                  <MarkdownRenderer content={taskDesc} />
                ) : (
                  <span className="text-gray-400 text-xs italic">Nothing to preview</span>
                )}
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

      {/* Kanban Board Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-50 p-4 rounded-xl space-y-3 border border-gray-200">
          <div className="flex items-center justify-between font-semibold text-gray-700 pb-2 border-b border-gray-200 text-sm">
            <span className="flex items-center gap-2"><ListTodo className="w-4 h-4 text-gray-500" /> To Do</span>
            <span className="bg-gray-200 text-gray-700 text-xs px-2 py-0.5 rounded-full">{tasks.filter((t) => t.status === "todo").length}</span>
          </div>
          <div className="space-y-3">
            {tasks.filter((t) => t.status === "todo").map(renderTaskCard)}
          </div>
        </div>

        <div className="bg-blue-50/40 p-4 rounded-xl space-y-3 border border-blue-100">
          <div className="flex items-center justify-between font-semibold text-blue-900 pb-2 border-b border-blue-100 text-sm">
            <span className="flex items-center gap-2"><Clock className="w-4 h-4 text-blue-500" /> In Progress</span>
            <span className="bg-blue-200 text-blue-800 text-xs px-2 py-0.5 rounded-full">{tasks.filter((t) => t.status === "in_progress").length}</span>
          </div>
          <div className="space-y-3">
            {tasks.filter((t) => t.status === "in_progress").map(renderTaskCard)}
          </div>
        </div>

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

      {/* Task Edit Modal */}
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

              <div className="border border-gray-200 rounded-lg p-2 space-y-2">
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
                  <div className="h-32 overflow-y-auto p-2 bg-gray-50 rounded">
                    {editTaskDesc ? (
                      <MarkdownRenderer content={editTaskDesc} />
                    ) : (
                      <span className="text-gray-400 text-xs italic">Nothing to preview</span>
                    )}
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
    </div>
  );
}