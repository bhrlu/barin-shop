import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";

export function useFavorites() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["favorites", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const { data, error } = await supabase
        .from("favorites")
        .select("product_id")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data.map((row) => row.product_id);
    },
  });

  const toggle = useMutation({
    mutationFn: async (productId: string) => {
      if (!user) throw new Error("برای ذخیره علاقه‌مندی وارد حساب شوید");
      const isFavorite = (query.data ?? []).includes(productId);
      if (isFavorite) {
        const { error } = await supabase
          .from("favorites")
          .delete()
          .eq("product_id", productId)
          .eq("user_id", user.id);
        if (error) throw error;
        return false;
      }
      const { error } = await supabase
        .from("favorites")
        .insert({ product_id: productId, user_id: user.id });
      if (error) throw error;
      return true;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return {
    ids: query.data ?? [],
    isFavorite: (id: string) => (query.data ?? []).includes(id),
    toggle,
  };
}