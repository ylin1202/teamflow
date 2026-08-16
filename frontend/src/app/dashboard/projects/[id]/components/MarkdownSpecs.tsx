"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Plus, Trash2, FileText, Edit2, X, Save, Eye } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";

export interface Document {
  id: string;
  project: string;
  title: string;
  content: string;
  updated_at: string;
}

interface MarkdownSpecsProps {
  projectId: string;
  canDelete: boolean;
}

export default function MarkdownSpecs({ projectId, canDelete }: MarkdownSpecsProps) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const [isAddingDoc, setIsAddingDoc] = useState(false);
  const [isDocLoading, setIsDocLoading] = useState(false);
  const [addDocTab, setAddDocTab] = useState<"edit" | "preview">("edit");

  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editDocTitle, setEditDocTitle] = useState("");
  const [editDocContent, setEditDocContent] = useState("");
  const [isEditDocLoading, setIsEditDocLoading] = useState(false);
  const [editDocTab, setEditDocTab] = useState<"edit" | "preview">("edit");

  const fetchDocs = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await api.get<Document[]>(`/api/documents/?project_id=${projectId}`);
      setDocs(res.data);
    } catch (err) {
      console.error("Failed to fetch document list", err);
    }
  }, [projectId]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

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
      console.error("Failed to create document", err);
    } finally {
      setIsDocLoading(false);
    }
  };

  const handleStartEditDoc = (doc: Document) => {
    setEditingDocId(doc.id);
    setEditDocTitle(doc.title);
    setEditDocContent(doc.content);
    setEditDocTab("edit");
  };

  const handleCancelEditDoc = () => {
    setEditingDocId(null);
    setEditDocTitle("");
    setEditDocContent("");
    setEditDocTab("edit");
  };

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
      console.error("Failed to update document", err);
    } finally {
      setIsEditDocLoading(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!confirm("Are you sure you want to delete this spec document?")) return;
    try {
      await api.delete(`/api/documents/${docId}/`);
      fetchDocs();
    } catch (err) {
      console.error("Failed to delete document", err);
    }
  };

  return (
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

      {isAddingDoc && (
        <form onSubmit={handleCreateDoc} className="bg-white p-5 border border-gray-200 rounded-xl shadow-sm space-y-4">
          <h3 className="font-semibold text-sm text-gray-800">Create New Spec / Document</h3>
          <input
            type="text"
            placeholder="Document Title (e.g. System Architecture Specification)"
            value={docTitle}
            onChange={(e) => setDocTitle(e.target.value)}
            className="w-full border rounded-lg p-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />

          <div className="border border-gray-200 rounded-lg p-2 space-y-2">
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
                placeholder="Write Markdown content here... (Supports # Heading, **bold**, lists, code blocks, tables)"
                value={docContent}
                onChange={(e) => setDocContent(e.target.value)}
                className="w-full border-none outline-none text-sm font-mono text-gray-800 h-64 resize-none p-2"
              />
            ) : (
              <div className="min-h-64 max-h-[500px] overflow-y-auto p-4 bg-gray-50/50 rounded-lg">
                {docContent ? (
                  <MarkdownRenderer content={docContent} />
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

      {docs.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-10 text-center text-gray-400 text-sm">
          No spec documents written for this project yet.
        </div>
      ) : (
        <div className="space-y-6">
          {docs.map((doc) => (
            <div key={doc.id} className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm space-y-4">
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

                  <div className="border border-gray-200 rounded-lg p-2 space-y-2">
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
                        className="w-full border-none outline-none text-sm font-mono text-gray-800 h-64 resize-none p-2"
                      />
                    ) : (
                      <div className="min-h-64 max-h-[500px] overflow-y-auto p-4 bg-gray-50/50 rounded-lg">
                        {editDocContent ? (
                          <MarkdownRenderer content={editDocContent} />
                        ) : (
                          <span className="text-gray-400 text-xs italic">Nothing to preview.</span>
                        )}
                      </div>
                    )}
                  </div>
                </form>
              ) : (
                <div>
                  <div className="border-b border-gray-100 pb-4 flex justify-between items-start">
                    <div>
                      <h3 className="font-bold text-gray-900 text-xl tracking-tight">{doc.title}</h3>
                      <span className="text-xs text-gray-400 mt-1 inline-block">
                        Last updated: {doc.updated_at ? new Date(doc.updated_at).toLocaleString() : "Just now"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleStartEditDoc(doc)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 hover:text-blue-600 transition shadow-sm"
                      >
                        <Edit2 className="w-3.5 h-3.5" /> Edit
                      </button>

                      {canDelete && (
                        <button
                          onClick={() => handleDeleteDoc(doc.id)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                          title="Delete Document"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="pt-4 text-gray-800 text-sm leading-relaxed">
                    <MarkdownRenderer content={doc.content || "*No content provided.*"} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}