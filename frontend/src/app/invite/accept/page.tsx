// invite/accept/page.tsx 完整修復版
"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import api from "@/lib/api";

export default function AcceptInvitePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");

  const [statusMsg, setStatusMsg] = useState("正在處理您的團隊邀請...");
  const [isError, setIsError] = useState(false);
  
  // 💡 用 useRef 防止 React StrictMode 觸發兩次 API
  const hasSubmitted = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatusMsg("無效或缺少邀請 Token。");
      setIsError(true);
      return;
    }

    if (hasSubmitted.current) return;
    hasSubmitted.current = true;

    // 💡 注意：ENDPOINT 改為 /api/accept-invitation/
    api.post("/api/accept-invitation/", { token })
      .then((res) => {
        setStatusMsg(`成功加入團隊「${res.data.organization_name}」！即將為您跳轉...`);
        setTimeout(() => {
          router.push("/dashboard");
        }, 2000);
      })
      .catch((err) => {
        setIsError(true);
        setStatusMsg(
          err.response?.data?.error || err.response?.data?.detail || "接受邀請失敗，請確認是否已登入對應帳號。"
        );
      });
  }, [token, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-200 max-w-md w-full text-center space-y-4">
        <h1 className="text-xl font-bold text-gray-800">團隊邀請驗證</h1>
        <p className={`text-sm ${isError ? "text-red-600 font-medium" : "text-gray-600"}`}>
          {statusMsg}
        </p>
      </div>
    </div>
  );
}