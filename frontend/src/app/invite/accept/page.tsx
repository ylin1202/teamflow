"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import api from "@/lib/api";

function AcceptInviteContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");

  const [statusMsg, setStatusMsg] = useState("Processing your team invitation...");
  const [isError, setIsError] = useState(false);
  
  // Prevent React StrictMode from triggering the API twice using useRef
  const hasSubmitted = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatusMsg("Invalid or missing invitation token.");
      setIsError(true);
      return;
    }

    if (hasSubmitted.current) return;
    hasSubmitted.current = true;

    // Endpoint: /api/accept-invitation/
    api.post("/api/accept-invitation/", { token })
      .then((res) => {
        setStatusMsg(`Successfully joined team "${res.data.organization_name}"! Redirecting...`);
        setTimeout(() => {
          router.push("/dashboard");
        }, 2000);
      })
      .catch((err) => {
        setIsError(true);
        setStatusMsg(
          err.response?.data?.error || err.response?.data?.detail || "Failed to accept invitation. Please ensure you are logged into the corresponding account."
        );
      });
  }, [token, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-200 max-w-md w-full text-center space-y-4">
        <h1 className="text-xl font-bold text-gray-800">Team Invitation Verification</h1>
        <p className={`text-sm ${isError ? "text-red-600 font-medium" : "text-gray-600"}`}>
          {statusMsg}
        </p>
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-200 max-w-md w-full text-center">
            <p className="text-sm text-gray-600">Loading invitation page...</p>
          </div>
        </div>
      }
    >
      <AcceptInviteContent />
    </Suspense>
  );
}