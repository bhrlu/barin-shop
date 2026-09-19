import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { api, getToken } from "@/lib/api";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async ({ location }) => {
    if (!getToken()) {
      throw redirect({ to: "/auth", search: { redirect: location.href } });
    }
    try {
      const user = await api.me();
      return { user };
    } catch {
      throw redirect({ to: "/auth", search: { redirect: location.href } });
    }
  },
  component: () => <Outlet />,
});
