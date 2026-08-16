import { withAuth } from "next-auth/middleware";

export default withAuth({
  pages: {
    signIn: "/login",
  },
});

// Protect only routes starting with /dashboard
export const config = {
  matcher: ["/dashboard/:path*"],
};