"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  // 若未登入自動導回登入頁
  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500 font-medium">載入使用者狀態中...</p>
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="mx-auto max-w-4xl rounded-xl bg-white p-6 shadow-md">
        <div className="flex items-center justify-between border-b pb-4">
          <h1 className="text-2xl font-bold text-gray-800">控制台 (Dashboard)</h1>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="rounded-md bg-red-500 px-4 py-2 text-sm text-white hover:bg-red-600 transition"
          >
            登出
          </button>
        </div>

        <div className="mt-6 space-y-4">
          {/* 使用者基本資訊 */}
          <div className="flex items-center space-x-4">
            {session.user?.image && (
              <img
                src={session.user.image}
                alt="Avatar"
                className="h-16 w-16 rounded-full"
              />
            )}
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {session.user?.name}
              </h2>
              <p className="text-sm text-gray-500">{session.user?.email}</p>
            </div>
          </div>

          {/* Django Backend JWT Token */}
          <div className="mt-6 rounded-lg bg-gray-50 p-4 border border-gray-200">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Django 後端核發之 JWT Token (Key)
            </h3>
            <p className="mt-2 break-all font-mono text-xs text-emerald-600 bg-emerald-50 p-2 rounded border border-emerald-200">
              {session.user?.backendToken || "未取得 Token (請檢查 next-auth callbacks)"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}