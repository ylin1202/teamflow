"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface Member {
  id: string;
  user_email?: string;
  email?: string;
  role: string;
  created_at: string;
}

interface Invitation {
  id: string;
  email: string;
  role: string;
  token?: string;
  is_accepted: boolean;
  created_at: string;
}

interface OrgQuotaUsage {
  plan: string;
  current_projects: number;
  max_projects: number;
}

// Plan member limit configurations (Free: 3 members, Pro/Enterprise: null for unlimited)
const PLAN_MEMBER_LIMITS: Record<string, number | null> = {
  FREE: 3,
  PRO: null,
  ENTERPRISE: null,
};

export default function TeamPage() {
  const { currentOrg } = useOrgStore();

  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [quota, setQuota] = useState<OrgQuotaUsage | null>(null);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState("MEMBER");
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // Only OWNER or ADMIN can send invitations, revoke invitations, and update member permissions
  const canManageTeam = currentOrg?.role === "OWNER" || currentOrg?.role === "ADMIN";

  const fetchTeamData = useCallback(async () => {
    if (!currentOrg) return;
    setIsLoading(true);
    try {
      const [membersRes, invitesRes, quotaRes] = await Promise.all([
        api.get<Member[]>("/api/org-members/"),
        api.get<Invitation[]>("/api/invitations/"),
        api.get<OrgQuotaUsage>("/api/billing/project-usage/", {
          headers: { "X-Organization-ID": currentOrg.id },
        }).catch(() => null), // Gracefully handle failure
      ]);

      setMembers(membersRes.data);
      setInvitations(invitesRes.data.filter((inv) => !inv.is_accepted));
      if (quotaRes) setQuota(quotaRes.data);
    } catch (err) {
      console.error("Failed to fetch team data", err);
    } finally {
      setIsLoading(false);
    }
  }, [currentOrg]);

  useEffect(() => {
    if (currentOrg) {
      fetchTeamData();
    }
  }, [currentOrg, fetchTeamData]);

  // Member quota calculations
  const currentPlan = quota?.plan?.toUpperCase() || currentOrg?.plan?.toUpperCase() || "FREE";
  const memberLimit = PLAN_MEMBER_LIMITS[currentPlan] ?? null; // null indicates unlimited
  const activeCount = members.length;
  const pendingCount = invitations.length;
  const totalOccupied = activeCount + pendingCount;
  
  // Check if member limit is reached (only applies to plans with limits)
  const isLimitReached = memberLimit !== null && totalOccupied >= memberLimit;

  // Send invitation
  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || isLimitReached) return;

    setIsSending(true);
    try {
      await api.post("/api/invitations/", { email, role });
      setEmail("");
      fetchTeamData();
      alert("Invitation sent successfully!");
    } catch (err: any) {
      console.error("Failed to send invitation", err);
      const errMsg =
        err.response?.data?.detail ||
        err.response?.data?.error ||
        "Failed to send invitation. Please verify whether the email is already in the team or the quota limit has been reached.";
      alert(errMsg);
    } finally {
      setIsSending(false);
    }
  };

  // Revoke invitation
  const handleCancelInvite = async (id: string) => {
    if (!window.confirm("Are you sure you want to cancel this invitation?")) return;
    try {
      await api.delete(`/api/invitations/${id}/`);
      fetchTeamData();
    } catch (err) {
      console.error("Failed to cancel invitation", err);
      alert("Failed to cancel invitation");
    }
  };

  // Update member role
  const handleUpdateRole = async (memberId: string, newRole: string) => {
    try {
      await api.patch(`/api/org-members/${memberId}/`, { role: newRole });
      fetchTeamData();
    } catch (err) {
      console.error("Failed to update role", err);
      alert("Failed to update permissions");
    }
  };

  // Remove member
  const handleRemoveMember = async (memberId: string) => {
    if (!window.confirm("Are you sure you want to remove this member from the team?")) return;
    try {
      await api.delete(`/api/org-members/${memberId}/`);
      fetchTeamData();
    } catch (err) {
      console.error("Failed to remove member", err);
      alert("Failed to remove member");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Team Members</h1>
          <p className="text-sm text-gray-500">
            Manage your organization members, roles, and pending invitations.
          </p>
        </div>

        {/* Team usage badge */}
        <div className="bg-white border rounded-xl px-4 py-2 text-xs font-medium shadow-sm flex items-center gap-3 w-fit">
          <span className="text-gray-500">Plan: <strong className="text-blue-600 uppercase">{currentPlan}</strong></span>
          <span className="text-gray-300">|</span>
          <span className="text-gray-700">
            Occupied: <strong className="text-gray-900">{totalOccupied}</strong>
            {memberLimit !== null ? ` / ${memberLimit} Members` : " (Unlimited)"}
          </span>
        </div>
      </div>

      {/* Quota limit warning banner */}
      {canManageTeam && isLimitReached && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-800">
          <div className="text-xs">
            <p className="font-bold text-sm">Team Member Limit Reached ({totalOccupied}/{memberLimit})</p>
            <p className="mt-0.5 text-amber-700">
              Your current plan ({currentPlan}) allows up to {memberLimit} team members (including active members and pending invitations).
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

      {/* 1. Invite Member Section */}
      {canManageTeam && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Invite New Member</h2>
          <form onSubmit={handleSendInvite} className="flex flex-col sm:flex-row gap-3">
            <input
              type="email"
              placeholder="colleague@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLimitReached}
              className="flex-1 rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              required
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              disabled={isLimitReached}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100 disabled:cursor-not-allowed"
            >
              <option value="MEMBER">Member</option>
              <option value="ADMIN">Admin</option>
            </select>
            <button
              type="submit"
              disabled={isSending || isLimitReached}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSending ? "Sending..." : isLimitReached ? "Quota Reached" : "Send Invitation"}
            </button>
          </form>
        </div>
      )}

      {/* 2. Pending Invitations Section */}
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

                  {canManageTeam && (
                    <button
                      onClick={() => handleCancelInvite(inv.id)}
                      className="text-xs text-red-600 hover:text-red-800 hover:underline"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Active Members Section */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 className="text-lg font-semibold text-gray-800">Active Members</h2>
          <span className="text-xs font-medium text-gray-400">Total: {members.length}</span>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-500">Loading members...</p>
        ) : (
          <div className="divide-y divide-gray-100 border rounded-lg overflow-hidden">
            {members.map((member) => {
              const displayEmail = member.user_email || member.email || "Unknown User";
              const joinedDate = member.created_at
                ? new Date(member.created_at).toLocaleDateString()
                : "Recently";

              return (
                <div key={member.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{displayEmail}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Joined: {joinedDate}
                    </p>
                  </div>

                  <div className="flex items-center space-x-3">
                    {canManageTeam && member.role !== "OWNER" ? (
                      <>
                        <select
                          value={member.role}
                          onChange={(e) => handleUpdateRole(member.id, e.target.value)}
                          className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
                        >
                          <option value="MEMBER">MEMBER</option>
                          <option value="ADMIN">ADMIN</option>
                        </select>
                        <button
                          onClick={() => handleRemoveMember(member.id)}
                          className="text-xs text-red-600 hover:text-red-800 hover:underline px-1"
                        >
                          Remove
                        </button>
                      </>
                    ) : (
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
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}