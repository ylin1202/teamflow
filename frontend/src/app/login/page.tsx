"use client";

import { signIn, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

function LoginContent() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (status === "authenticated" && session) {
      router.push("/dashboard");
    }
  }, [session, status, router]);

  const handleGoogleSignIn = () => {
    setIsLoading(true);
    signIn("google", { callbackUrl: "/dashboard" });
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-slate-50/50 px-4 overflow-hidden selection:bg-blue-500 selection:text-white">
      {/* 🔮 背景柔和光暈（淺藍與靛藍） */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-tr from-blue-100/60 to-indigo-100/40 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute -bottom-10 right-1/4 w-96 h-96 bg-blue-50/80 blur-[100px] rounded-full pointer-events-none" />

      {/* 登入主要卡片 */}
      <div className="relative z-10 max-w-md w-full backdrop-blur-md bg-white/90 border border-slate-200/80 p-8 sm:p-10 rounded-2xl shadow-xl shadow-slate-200/50">
        
        {/* 品牌識別與標題 */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center h-13 w-13 rounded-2xl bg-blue-600 text-white font-bold text-2xl shadow-md shadow-blue-500/20">
            T
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              登入 <span className="text-blue-600">TeamFlow</span>
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              團隊協作與專案管理平台
            </p>
          </div>
        </div>

        {/* 登入按鈕區塊 */}
        <div className="mt-8">
          <button
            onClick={handleGoogleSignIn}
            disabled={isLoading || status === "loading"}
            className="group w-full flex items-center justify-center gap-3 px-5 py-3.5 rounded-xl border border-slate-200 bg-white text-sm font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 active:scale-[0.99] transition-all duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {isLoading ? (
              <div className="w-5 h-5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-5 h-5 transition-transform duration-200 group-hover:scale-110" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
            )}
            <span>{isLoading ? "正在連線至 Google..." : "使用 Google 帳號快速登入"}</span>
          </button>
        </div>

        {/* 亮點特性標籤 */}
        <div className="mt-8 pt-6 border-t border-slate-100 flex justify-center items-center gap-4 text-xs text-slate-500 font-medium">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            多組織隔離
          </span>
          <span className="text-slate-300">•</span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            RBAC 角色管理
          </span>
          <span className="text-slate-300">•</span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
            Stripe 整合
          </span>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <LoginContent />;
}