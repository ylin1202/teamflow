"use client";

import { useSession, signOut } from "next-auth/react";
import OrgSwitcher from "./OrgSwitcher";

export default function Header() {
  const { data: session } = useSession();

  return (
    <header className="h-16 bg-white border-b border-gray-200 px-6 flex items-center justify-between sticky top-0 z-10">
      {/* Left: Organization Switcher */}
      <div className="flex items-center space-x-4">
        <OrgSwitcher />
      </div>

      {/* Right: User Information & Sign Out */}
      <div className="flex items-center space-x-4">
        <span className="text-xs font-medium text-gray-500 hidden sm:inline">
          {session?.user?.email}
        </span>
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="text-xs text-gray-600 hover:text-red-600 font-medium px-3 py-1.5 rounded-md hover:bg-red-50 transition border border-gray-200"
        >
          Logout
        </button>
      </div>
    </header>
  );
}