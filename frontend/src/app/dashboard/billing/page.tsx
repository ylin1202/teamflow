"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useOrgStore } from "@/store/useOrgStore";
import api from "@/lib/api";

interface OrgProjectUsage {
  plan: string;
  current_projects: number;
  max_projects: number;
}

const PLANS = [
  {
    key: "FREE",
    level: 1,
    name: "Free Tier",
    priceId: "",
    price: "$0",
    projectLimit: 5,
    memberLimit: 3, // Team member limit: 3
    features: [
      "Up to 5 Projects",
      "Up to 3 Team Members",
    ],
  },
  {
    key: "PRO",
    level: 2,
    name: "Pro Plan",
    priceId: "price_1TydLmCNxWb8kewb67uOfeOK",
    price: "$29",
    period: "/ one-time",
    projectLimit: 25,
    memberLimit: null, // Unlimited members
    features: [
      "Up to 25 Projects",
      "Unlimited Team Members",
    ],
    isPopular: true,
  },
  {
    key: "ENTERPRISE",
    level: 3,
    name: "Enterprise",
    priceId: "price_1TydLXCNxWb8kewbppCnxt9M",
    price: "$50",
    period: "/ one-time",
    projectLimit: 150,
    memberLimit: null, // Unlimited members
    features: [
      "Up to 150 Projects",
      "Unlimited Team Members",
    ],
  },
];

function BillingContent() {
  const { currentOrg, fetchOrganizations } = useOrgStore();
  const searchParams = useSearchParams();
  const [usage, setUsage] = useState<OrgProjectUsage | null>(null);
  const [loadingPriceId, setLoadingPriceId] = useState<string | null>(null);

  // 1. Fetch current organization's project usage count and plan details
  const fetchUsage = useCallback(async () => {
    if (!currentOrg?.id || currentOrg.role !== "OWNER") return;
    try {
      const config = {
        headers: { "X-Organization-ID": currentOrg.id },
      };
      const res = await api.get<OrgProjectUsage>("/api/billing/project-usage/", config);
      setUsage(res.data);
    } catch (err) {
      console.error("Failed to fetch project quota status", err);
    }
  }, [currentOrg?.id, currentOrg?.role]);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  // 2. Listen for Stripe redirect URL containing ?success=true to refresh Org Store and usage data
  useEffect(() => {
    if (searchParams.get("success") === "true") {
      fetchUsage();
      if (fetchOrganizations) {
        fetchOrganizations();
      }
    }
  }, [searchParams, fetchUsage, fetchOrganizations]);

  // Access Control: Display Access Denied view for non-OWNER roles
  if (currentOrg && currentOrg.role !== "OWNER") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4 text-center">
        <div className="p-4 bg-red-50 rounded-full text-red-600 border border-red-100">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-12 h-12"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-800">Access Denied</h1>
        <p className="text-sm text-gray-500 max-w-md">
          Billing and subscription management is restricted to organization Owners only. If you need to upgrade or modify your plan, please contact your organization owner.
        </p>
      </div>
    );
  }

  // 3. Trigger Stripe One-time Checkout
  const handleSubscribe = async (priceId: string) => {
    if (!priceId || !currentOrg?.id) return;
    setLoadingPriceId(priceId);

    try {
      const config = {
        headers: { "X-Organization-ID": currentOrg.id },
      };
      const res = await api.post<{ url: string }>(
        "/api/billing/checkout/",
        { price_id: priceId },
        config
      );
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      console.error("Failed to create Checkout Session", err);
      alert("Unable to initiate checkout. Please check your permissions or Stripe configuration.");
    } finally {
      setLoadingPriceId(null);
    }
  };

  // Critical resolution: Prioritize latest plan returned by usage API, fallback to currentOrg.plan
  const currentPlanKey = usage?.plan?.toUpperCase() || currentOrg?.plan?.toUpperCase() || "FREE";
  
  // Get current plan tier level (FREE=1, PRO=2, ENTERPRISE=3)
  const currentLevel = PLANS.find((p) => p.key === currentPlanKey)?.level || 1;

  const currentUsed = usage?.current_projects ?? 0;
  const currentLimit = usage?.max_projects ?? (currentPlanKey === "PRO" ? 25 : currentPlanKey === "ENTERPRISE" ? 150 : 5);
  const usedPercentage = Math.min(100, Math.round((currentUsed / currentLimit) * 100));

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
          Manage your workspace plan and project quota limits.
        </p>
      </div>

      {/* Current project usage card */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm flex flex-col justify-between gap-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-100 uppercase">
              Current Plan: {currentPlanKey}
            </span>
            <h2 className="text-xl font-bold text-gray-800 mt-2">
              Status: <span className="text-emerald-600 capitalize">Active</span>
            </h2>
          </div>

          <div>
            <span className="text-xs text-gray-500">Project Quota</span>
            <p className="text-lg font-bold text-gray-800">
              {currentLimit} Projects Max
            </p>
          </div>
        </div>

        {/* Project usage progress bar */}
        <div className="border-t border-gray-100 pt-4">
          <div className="flex justify-between items-center text-xs text-gray-600 mb-1.5 font-medium">
            <span>Active Projects Usage</span>
            <span>
              <strong className="text-gray-900">{currentUsed}</strong> / {currentLimit} Projects
            </span>
          </div>

          <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-2.5 rounded-full transition-all duration-500 ${progressBarColor}`}
              style={{ width: `${usedPercentage}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* Plan selection matrix (Pricing Cards) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {PLANS.map((plan) => {
          const isCurrent = currentPlanKey === plan.key;
          const isLowerLevel = plan.level < currentLevel;

          let buttonText = "Buy Plan";
          let isDisabled = false;

          if (isCurrent) {
            buttonText = "Current Plan";
            isDisabled = true;
          } else if (isLowerLevel) {
            buttonText = "Included in Plan";
            isDisabled = true;
          } else if (loadingPriceId === plan.priceId) {
            buttonText = "Processing...";
            isDisabled = true;
          } else {
            buttonText = "Upgrade Plan";
          }

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
              {plan.isPopular && !isCurrent && !isLowerLevel && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-[10px] font-bold tracking-wide uppercase px-3 py-1 rounded-full">
                  Most Popular
                </span>
              )}

              {isCurrent && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-[10px] font-bold tracking-wide uppercase px-3 py-1 rounded-full">
                  Your Current Plan
                </span>
              )}

              <div>
                <h3 className="text-lg font-bold text-gray-800">{plan.name}</h3>
                <div className="mt-4 flex items-baseline">
                  <span className="text-3xl font-extrabold text-gray-900">{plan.price}</span>
                  {plan.period && <span className="text-xs text-gray-500 ml-1">{plan.period}</span>}
                </div>

                <ul className="mt-6 space-y-3 text-xs text-gray-600">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center space-x-2">
                      <span className="text-emerald-500 font-bold">✓</span>
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button
                onClick={() => handleSubscribe(plan.priceId)}
                disabled={isDisabled || !plan.priceId}
                className={`mt-8 w-full rounded-lg py-2.5 text-xs font-semibold transition ${
                  isCurrent || isLowerLevel
                    ? "bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200"
                    : loadingPriceId === plan.priceId
                    ? "bg-blue-400 text-white cursor-wait"
                    : "bg-blue-600 text-white hover:bg-blue-700 shadow-sm"
                }`}
              >
                {buttonText}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function BillingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-64 items-center justify-center text-sm text-gray-500">
          Loading billing details...
        </div>
      }
    >
      <BillingContent />
    </Suspense>
  );
}