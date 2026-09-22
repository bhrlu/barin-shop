import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type NotificationQuery } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Query keys are scoped by user id, so a sign-out/sign-in on the same tab never
 * shows the previous account's inbox; invalidating `all(userId)` refreshes the
 * header bell and the account page together. */
export const notificationKeys = {
  all: (userId: string | undefined) => ["notifications", userId] as const,
  unread: (userId: string | undefined) => ["notifications", userId, "unread-count"] as const,
  list: (userId: string | undefined, query: NotificationQuery) =>
    ["notifications", userId, "list", query] as const,
};

/** How often the bell re-reads the unread count (there is no push channel). */
const UNREAD_POLL_MS = 60_000;

export function useUnreadNotifications() {
  const { user } = useAuth();
  return useQuery({
    queryKey: notificationKeys.unread(user?.id),
    queryFn: () => api.notificationsUnreadCount(),
    enabled: Boolean(user),
    refetchInterval: UNREAD_POLL_MS,
    retry: false,
  });
}

export function useNotificationList(query: NotificationQuery, enabled = true) {
  const { user } = useAuth();
  return useQuery({
    queryKey: notificationKeys.list(user?.id, query),
    queryFn: () => api.notifications(query),
    enabled: Boolean(user) && enabled,
  });
}

/** Mark one / all as read; both refresh every notification query of this user. */
export function useNotificationActions() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: notificationKeys.all(user?.id) });

  const markRead = useMutation({
    mutationFn: (id: string) => api.markNotificationRead(id),
    onSuccess: () => void refresh(),
    onError: () => toast.error("علامت‌گذاری اعلان انجام نشد"),
  });
  const markAllRead = useMutation({
    mutationFn: () => api.markAllNotificationsRead(),
    onSuccess: () => void refresh(),
    onError: () => toast.error("علامت‌گذاری اعلان‌ها انجام نشد"),
  });
  return { markRead, markAllRead };
}
