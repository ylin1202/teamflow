"use client";

import { useState, useEffect, useCallback } from "react";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface Member {
  id: string;
  user_email: string;
  role: string;
  created_at: string;
}

interface Invitation {
  id: string;
  email: string;
  role: string;
  is_accepted: boolean;
  created_at: string;
}

export default function TeamPage() {
  const { currentOrg } = useOrgStore();

  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("MEMBER");
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // 只有 OWNER 或 ADMIN 才能管理邀請
  const canManageTeam = currentOrg?.role === "OWNER" || currentOrg?.role === "ADMIN";

  const fetchTeamData = useCallback(async () => {
    if (!currentOrg) return;
    setIsLoading(true);
    try {
      const [membersRes, invitesRes] = await Promise.all([
        api.get<Member[]>("/api/org-members/"),
        canManageTeam ? api.get<Invitation[]>("/api/invitations/") : Promise.resolve({ data: [] }),
      ]);

      setMembers(membersRes.data);
      setInvitations(invitesRes.data.filter((inv) => !inv.is_accepted));
    } catch (err) {
      console.error("無法取得團隊資料", err);
    } finally {
      setIsLoading(false);
    }
  }, [currentOrg, canManageTeam]);

  useEffect(() => {
    if (currentOrg) {
      fetchTeamData();
    }
  }, [currentOrg, fetchTeamData]);

  // 發送邀請
  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setIsSending(true);
    try {
      await api.post("/api/invitations/", { email, role });
      setEmail("");
      fetchTeamData(); // 重新抓取資料，這步非常重要
    } catch (err) {
      console.error("發送邀請失敗", err);
      alert("發送邀請失敗，請確認該 Email 是否已在團隊或已受邀。");
    } finally {
      setIsSending(false);
    }
  };

  // 撤回邀請
  const handleCancelInvite = async (id: string) => {
    try {
      await api.delete(`/api/invitations/${id}/`);
      fetchTeamData();
    } catch (err) {
      console.error("取消邀請失敗", err);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Team Members</h1>
        <p className="text-sm text-gray-500">
          Manage your organization members, roles, and pending invitations.
        </p>
      </div>

      {/* 1. 發送邀請區塊 */}
      {canManageTeam && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Invite New Member</h2>
          <form onSubmit={handleSendInvite} className="flex flex-col sm:flex-row gap-3">
            <input
              type="email"
              placeholder="colleague@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="MEMBER">Member</option>
              <option value="ADMIN">Admin</option>
            </select>
            <button
              type="submit"
              disabled={isSending}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition disabled:opacity-50"
            >
              {isSending ? "Sending..." : "Send Invitation"}
            </button>
          </form>
        </div>
      )}

      {/* 2. 待處理邀請 (Pending Invitations) 區塊 */}
      {canManageTeam && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b pb-3">
            <h2 className="text-lg font-semibold text-gray-800">Pending Invitations</h2>
            <span className="text-xs font-medium text-gray-400">Total: {invitations.length}</span>
          </div>

          {isLoading ? (
            <p className="text-sm text-gray-500">Loading invitations...</p>
          ) : invitations.length === 0 ? (
            <p className="text-sm text-gray-400 py-2">No pending invitations.</p>
          ) : (
            <div className="divide-y divide-gray-100 border rounded-lg overflow-hidden">
              {invitations.map((inv) => (
                <div key={inv.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{inv.email}</p>
                    <p className="text-xs text-gray-400 mt-0.5">Role: {inv.role}</p>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="text-xs bg-yellow-50 text-yellow-700 font-medium px-2.5 py-1 rounded-full border border-yellow-200">
                      Pending
                    </span>
                    <button
                      onClick={() => handleCancelInvite(inv.id)}
                      className="text-xs text-red-600 hover:text-red-800 hover:underline"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 3. 正式成員 (Active Members) 區塊 */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 className="text-lg font-semibold text-gray-800">Active Members</h2>
          <span className="text-xs font-medium text-gray-400">Total: {members.length}</span>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-500">Loading members...</p>
        ) : (
          <div className="divide-y divide-gray-100 border rounded-lg overflow-hidden">
            {members.map((member) => (
              <div key={member.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                <div>
                  <p className="text-sm font-semibold text-gray-800">{member.user_email}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Joined: {new Date(member.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span
                  className={`text-xs font-bold px-3 py-1 rounded-full ${
                    member.role === "OWNER"
                      ? "bg-purple-100 text-purple-700"
                      : member.role === "ADMIN"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-100 text-gray-700"
                  }`}
                >
                  {member.role}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}