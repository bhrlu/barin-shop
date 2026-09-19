import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function useFavorites() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["favorites", user?.id],
    enabled: !!user,
    queryFn: () => api.favorites(),
  });

  const toggle = useMutation({
    mutationFn: async (productId: string) => {
      if (!user) throw new Error("برای ذخیره علاقه‌مندی وارد حساب شوید");
      const result = await api.toggleFavorite(productId);
      return result.is_favorite;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return {
    ids: query.data ?? [],
    isFavorite: (id: string) => (query.data ?? []).includes(id),
    toggle,
  };
}
