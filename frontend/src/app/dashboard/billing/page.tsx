"use client";

import { useState, useEffect, useCallback } from "react";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface SubscriptionInfo {
  plan: string;
  status: string;
  monthly_api_quota: number;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
}

interface QuotaUsage {
  used: number;
  limit: number;
  remaining: number;
  percentage: number;
  month: string;
}

const PLANS = [
  {
    key: "free",
    name: "Free Tier",
    priceId: "",
    price: "$0",
    quota: "1,000 API calls/mo",
    features: ["Up to 3 Team Members", "Community Support", "Basic Analytics"],
  },
  {
    key: "pro",
    name: "Pro Plan",
    priceId: "price_1TxXgaCNxWb8kewbGkYFsc40",
    price: "$29",
    period: "/month",
    quota: "50,000 API calls/mo",
    features: [
      "Access to 50,000 API calls/mo",
      "Unlimited Team Members",
      "Priority Support",
      "Advanced Analytics & 99.9% SLA",
    ],
    isPopular: true,
  },
  {
    key: "enterprise",
    name: "Enterprise",
    priceId: "price_1TxXi5CNxWb8kewbtKDELVkY",
    price: "$99",
    period: "/month",
    quota: "500,000 API calls/mo",
    features: [
      "Access to 500,000 API calls/mo",
      "Custom Integrations",
      "Dedicated Account Manager",
      "Custom SLA & Audit Logs",
    ],
  },
];

export default function BillingPage() {
  const { currentOrg } = useOrgStore();
  const [subInfo, setSubInfo] = useState<SubscriptionInfo | null>(null);
  const [usage, setUsage] = useState<QuotaUsage | null>(null);
  const [loadingPriceId, setLoadingPriceId] = useState<string | null>(null);
  const [loadingCancel, setLoadingCancel] = useState(false);
  const [loadingReactivate, setLoadingReactivate] = useState(false);
  const [loadingPortal, setLoadingPortal] = useState(false);

  // 1. 抓取訂閱狀態與用量
  const fetchSubscription = useCallback(async () => {
    if (!currentOrg?.id) return;
    try {
      const config = {
        headers: {
          "X-Organization-ID": currentOrg.id,
        },
      };

      const [subRes, usageRes] = await Promise.all([
        api.get<SubscriptionInfo>("/api/billing/subscription/", config),
        api.get<QuotaUsage>("/api/billing/usage/", config).catch(() => null),
      ]);

      setSubInfo(subRes.data);
      if (usageRes?.data) {
        setUsage(usageRes.data);
      }
    } catch (err) {
      console.error("無法取得訂閱或用量狀態", err);
    }
  }, [currentOrg?.id]);

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

  // 2. 訂閱 / 升級
  const handleSubscribe = async (priceId: string) => {
    if (!priceId) return;
    setLoadingPriceId(priceId);

    try {
      const res = await api.post<{ url: string }>("/api/billing/checkout/", {
        price_id: priceId,
      });
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      console.error("建立 Checkout Session 失敗", err);
      alert("無法啟動付款程序，請確認 Stripe API 金鑰設定。");
    } finally {
      setLoadingPriceId(null);
    }
  };

  // 3. 取消訂閱
  const handleCancelSubscription = async () => {
    const confirmed = window.confirm(
      "確定要取消訂閱嗎？取消後，本月剩餘時間仍可繼續使用，期滿後將自動降級至 Free 方案。"
    );

    if (!confirmed) return;

    setLoadingCancel(true);
    try {
      await api.delete("/api/billing/subscription/cancel/");
      alert("已成功設定取消訂閱，將於本月期滿後自動停止扣款。");
      fetchSubscription();
    } catch (err) {
      console.error("取消訂閱失敗", err);
      alert("取消失敗，請稍後再試。");
    } finally {
      setLoadingCancel(false);
    }
  };

  // 4. 恢復自動續訂 (Reactivate)
  const handleReactivateSubscription = async () => {
    setLoadingReactivate(true);
    try {
      await api.post("/api/billing/subscription/reactivate/");
      alert("已成功恢復自動續訂！");
      fetchSubscription();
    } catch (err) {
      console.error("恢復續訂失敗", err);
      alert("恢復失敗，請稍後再試。");
    } finally {
      setLoadingReactivate(false);
    }
  };

  // 5. 前往 Stripe Billing Portal 管理信用卡/發票
  const handleOpenPortal = async () => {
    setLoadingPortal(true);
    try {
      const res = await api.post<{ url: string }>("/api/billing/portal/");
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      console.error("開啟 Billing Portal 失敗", err);
      alert("無法開啟付款管理介面，請稍後再試。");
    } finally {
      setLoadingPortal(false);
    }
  };

  const currentPlanKey = subInfo?.plan?.toLowerCase() || "free";
  const isCanceling = subInfo?.status === "canceling" || subInfo?.cancel_at_period_end;
  const isPastDue = subInfo?.status === "past_due";

  const currentLimit = usage?.limit ?? subInfo?.monthly_api_quota ?? 1000;
  const currentUsed = usage?.used ?? 0;
  const usedPercentage = usage?.percentage ?? (currentLimit > 0 ? Math.round((currentUsed / currentLimit) * 100) : 0);

  const progressBarColor =
    usedPercentage >= 90
      ? "bg-red-500"
      : usedPercentage >= 75
      ? "bg-amber-500"
      : "bg-blue-600";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Billing & Plans</h1>
        <p className="text-sm text-gray-500">
          Manage your workspace subscription, API quota, and billing status.
        </p>
      </div>

      {/* ⚠️ 扣款失敗警示 Banner (Past Due) */}
      {isPastDue && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <span className="text-xl">⚠️</span>
            <div>
              <h3 className="font-bold text-sm">Payment Failed</h3>
              <p className="text-xs text-red-600 mt-0.5">
                Your latest subscription payment has failed. Please update your payment details to retain access.
              </p>
            </div>
          </div>
          <button
            onClick={handleOpenPortal}
            disabled={loadingPortal}
            className="px-3.5 py-1.5 text-xs font-semibold bg-red-600 text-white rounded-lg hover:bg-red-700 transition shadow-sm whitespace-nowrap"
          >
            {loadingPortal ? "Opening..." : "Update Payment Method"}
          </button>
        </div>
      )}

      {/* ⚠️ 訂閱即將到期警示 Banner (Canceling) */}
      {isCanceling && !isPastDue && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <span className="text-xl">⏳</span>
            <div>
              <h3 className="font-bold text-sm">Subscription Canceling</h3>
              <p className="text-xs text-amber-700 mt-0.5">
                Your {subInfo?.plan} plan will be downgraded to Free at the end of the current billing cycle.
              </p>
            </div>
          </div>
          <button
            onClick={handleReactivateSubscription}
            disabled={loadingReactivate}
            className="px-3.5 py-1.5 text-xs font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition shadow-sm whitespace-nowrap"
          >
            {loadingReactivate ? "Processing..." : "Reactivate Subscription"}
          </button>
        </div>
      )}

      {/* 當前訂閱狀態卡片 */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm flex flex-col justify-between gap-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-100 uppercase">
                Current Plan: {subInfo?.plan || "FREE"}
              </span>
              {isPastDue && (
                <span className="text-xs font-semibold text-red-600 bg-red-100 px-2.5 py-1 rounded-full uppercase">
                  Past Due
                </span>
              )}
            </div>

            <h2 className="text-xl font-bold text-gray-800 mt-2">
              Status: <span className="capitalize">{isCanceling ? "Canceling at Period End" : subInfo?.status || "Active"}</span>
            </h2>
          </div>

          <div className="text-left md:text-right flex flex-col md:flex-row items-start md:items-center gap-6">
            <div>
              <span className="text-xs text-gray-500">Monthly Limit</span>
              <p className="text-lg font-bold text-gray-800">
                {currentLimit.toLocaleString()} calls
              </p>
            </div>

            {/* 右側按鈕區（帶 Tooltip） */}
            {currentPlanKey !== "free" && (
              <div className="flex items-center space-x-2 mt-2 md:mt-0">
                {isCanceling ? (
                  <button
                    onClick={handleReactivateSubscription}
                    disabled={loadingReactivate}
                    className="text-xs font-semibold px-3 py-1.5 rounded-lg transition border shadow-sm bg-amber-50 text-amber-700 hover:bg-amber-100 border-amber-200"
                  >
                    {loadingReactivate ? "Processing..." : "Reactivate"}
                  </button>
                ) : (
                  <button
                    onClick={handleCancelSubscription}
                    disabled={loadingCancel}
                    className="text-xs font-semibold px-3 py-1.5 rounded-lg transition border shadow-sm bg-red-50 text-red-600 hover:bg-red-100 border-red-200"
                  >
                    {loadingCancel ? "Processing..." : "Cancel Subscription"}
                  </button>
                )}

                {/* 帶 Tooltip 的按鈕區塊 */}
                <div className="relative group inline-block">
                  <button
                    onClick={handleOpenPortal}
                    disabled={loadingPortal}
                    className="text-xs font-semibold px-3 py-1.5 rounded-lg transition border shadow-sm bg-gray-50 text-gray-700 hover:bg-gray-100 border-gray-200 flex items-center space-x-1"
                  >
                    <span>{loadingPortal ? "Loading..." : "Manage Payment & Invoices"}</span>
                    <span className="text-[10px] opacity-60">↗</span>
                  </button>

                  {/* 滑鼠懸停時顯示的浮動黑色 Tooltip */}
                  <div className="absolute right-0 top-full mt-2 hidden group-hover:flex flex-col items-end z-20 w-64 pointer-events-none">
                    <div className="bg-gray-900 text-white text-[11px] leading-relaxed p-2.5 rounded-lg shadow-xl border border-gray-800 text-left">
                      You will be redirected to our secure payment partner (Stripe) to manage your cards and invoices.
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* API 用量進度條 */}
        <div className="border-t border-gray-100 pt-4">
          <div className="flex justify-between items-center text-xs text-gray-600 mb-1.5 font-medium">
            <span>API Usage this month ({usage?.month || "Current Period"})</span>
            <span>
              <strong className="text-gray-900">{currentUsed.toLocaleString()}</strong> /{" "}
              {currentLimit.toLocaleString()} calls ({usedPercentage}%)
            </span>
          </div>

          <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-2.5 rounded-full transition-all duration-500 ${progressBarColor}`}
              style={{ width: `${Math.min(100, usedPercentage)}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* 方案選擇矩陣 (Pricing Table) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {PLANS.map((plan) => {
          const isCurrent = currentPlanKey === plan.key;

          return (
            <div
              key={plan.name}
              className={`rounded-2xl border p-6 flex flex-col justify-between relative bg-white ${
                isCurrent
                  ? "border-blue-600 shadow-lg ring-2 ring-blue-500"
                  : plan.isPopular
                  ? "border-blue-400 shadow-md"
                  : "border-gray-200"
              }`}
            >
              {plan.isPopular && !isCurrent && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-[10px] font-bold tracking-wide uppercase px-3 py-1 rounded-full">
                  Most Popular
                </span>
              )}

              {isCurrent && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-green-600 text-white text-[10px] font-bold tracking-wide uppercase px-3 py-1 rounded-full">
                  Your Current Plan
                </span>
              )}

              <div>
                <h3 className="text-lg font-bold text-gray-800">{plan.name}</h3>
                <div className="mt-4 flex items-baseline">
                  <span className="text-3xl font-extrabold text-gray-900">{plan.price}</span>
                  {plan.period && <span className="text-xs text-gray-500 ml-1">{plan.period}</span>}
                </div>
                <p className="text-xs font-medium text-blue-600 mt-2">{plan.quota}</p>

                <ul className="mt-6 space-y-3 text-xs text-gray-600">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center space-x-2">
                      <span className="text-green-500 font-bold">✓</span>
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button
                onClick={() => handleSubscribe(plan.priceId)}
                disabled={isCurrent || !plan.priceId || loadingPriceId === plan.priceId}
                className={`mt-8 w-full rounded-lg py-2.5 text-xs font-semibold transition ${
                  isCurrent
                    ? "bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200"
                    : loadingPriceId === plan.priceId
                    ? "bg-blue-400 text-white cursor-wait"
                    : plan.isPopular
                    ? "bg-blue-600 text-white hover:bg-blue-700"
                    : "bg-gray-800 text-white hover:bg-gray-900"
                }`}
              >
                {isCurrent
                  ? "Current Plan"
                  : loadingPriceId === plan.priceId
                  ? "Processing..."
                  : "Upgrade Plan"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}