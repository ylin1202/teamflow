"use client";

import { useState, useEffect, useCallback } from "react";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface SubscriptionInfo {
  plan: string;
  status: string;
  monthly_api_quota: number;
  current_period_end?: string;
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
  const [loadingPriceId, setLoadingPriceId] = useState<string | null>(null);

  const fetchSubscription = useCallback(async () => {
    if (!currentOrg) return;
    try {
      const res = await api.get<SubscriptionInfo>("/api/billing/subscription/");
      setSubInfo(res.data);
    } catch (err) {
      console.error("無法取得訂閱狀態", err);
    }
  }, [currentOrg]);

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

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

  // 💡 取得當前平臺的 Plan Key (轉小寫，後端可能是 "PRO" 或 "pro")
  const currentPlanKey = subInfo?.plan?.toLowerCase() || "free";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Billing & Plans</h1>
        <p className="text-sm text-gray-500">
          Manage your workspace subscription, API quota, and billing status.
        </p>
      </div>

      {/* 當前訂閱狀態卡片 */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-100 uppercase">
            Current Plan: {subInfo?.plan || "FREE"}
          </span>
          <h2 className="text-xl font-bold text-gray-800 mt-2">
            Status: <span className="capitalize">{subInfo?.status || "Active"}</span>
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            Monthly API Quota:{" "}
            <strong className="text-gray-700">
              {subInfo?.monthly_api_quota !== undefined && subInfo?.monthly_api_quota !== null
                ? subInfo.monthly_api_quota.toLocaleString()
                : "1,000"}
            </strong>{" "}
            calls
          </p>
        </div>
      </div>

      {/* 方案選擇矩陣 (Pricing Table) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {PLANS.map((plan) => {
          // 💡 動態判斷這張卡片是否為當前用戶的方案
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

              {/* 💡 根據動態判斷 renders 按鈕 */}
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