import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { type ItemsDeleteResponse, ItemsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteItemsProps {
  selectedIds: string[]
  onDeleted: () => void
}

const DeleteItems = ({ selectedIds, onDeleted }: DeleteItemsProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (ids: string[]) =>
      ItemsService.deleteItems({ requestBody: { ids } }),
    onSuccess: (response: ItemsDeleteResponse) => {
      const { deleted_count, skipped = [] } = response
      const parts: string[] = []

      if (deleted_count > 0) {
        parts.push(
          `Deleted ${deleted_count} item${deleted_count === 1 ? "" : "s"}.`,
        )
      }
      if (skipped.length > 0) {
        const reasons = Array.from(new Set(skipped.map((s) => s.reason)))
        parts.push(
          `${skipped.length} item${skipped.length === 1 ? "" : "s"} skipped (${reasons.join("; ")}).`,
        )
      }
      const message = parts.join(" ")

      if (deleted_count > 0) {
        showSuccessToast(message)
      } else {
        showErrorToast(message || "No items were deleted.")
      }

      setIsOpen(false)
      onDeleted()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] })
    },
  })

  const count = selectedIds.length

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm" disabled={count === 0}>
          <Trash2 className="mr-2 h-4 w-4" />
          Delete selected ({count})
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete {count} item{count === 1 ? "" : "s"}</DialogTitle>
          <DialogDescription>
            {count === 1
              ? "This item will be permanently deleted."
              : `These ${count} items will be permanently deleted.`}{" "}
            Are you sure? You will not be able to undo this action. Items you are
            not allowed to delete will be skipped.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={mutation.isPending}
            onClick={() => mutation.mutate(selectedIds)}
          >
            Delete
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteItems
