import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type TxnPatch } from "./api";

/** PATCH a transaction, then refresh everything derived from it (budget, S-Corp, summary). */
export function useUpdateTxn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: TxnPatch }) => api.updateTransaction(id, patch),
    onSuccess: () => queryClient.invalidateQueries(),
  });
}
