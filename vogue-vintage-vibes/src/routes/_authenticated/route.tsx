import { createFileRoute, Outlet, useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { api, getToken, type UserInfo } from "@/lib/api";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  // F5.13: no `throw redirect()` here. On a direct page load this route is not
  // server-rendered, and a redirect thrown during that first client pass swapped
  // the matched tree to /auth while React was still hydrating the server HTML
  // («Hydration failed»). The guard resolves instead, and the layout below
  // redirects once after mount — an ordinary client navigation. Nothing under
  // this route renders (or fetches) without a user.
  beforeLoad: async (): Promise<{ user: UserInfo | null }> => {
    if (!getToken()) return { user: null };
    try {
      return { user: await api.me() };
    } catch {
      return { user: null };
    }
  },
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  const { user } = Route.useRouteContext();
  const navigate = useNavigate();
  // the protected URL as first rendered: while the redirect is in flight
  // `useLocation()` already reports /auth, which must not become the target
  const target = useRef(useLocation().href);

  useEffect(() => {
    if (!user) {
      void navigate({ to: "/auth", search: { redirect: target.current }, replace: true });
    }
  }, [user, navigate]);

  return user ? <Outlet /> : null;
}
