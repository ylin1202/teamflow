import { withAuth } from "next-auth/middleware";

export default withAuth({
  pages: {
    signIn: "/login",
  },
});

// 只有 /dashboard 開頭的頁面需要登入防護
export const config = {
  matcher: ["/dashboard/:path*"],
};