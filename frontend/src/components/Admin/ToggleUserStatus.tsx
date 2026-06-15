import { useMutation, useQueryClient } from "@tanstack/react-query"
import { UserCheck, UserX } from "lucide-react"
import { useState } from "react"

import { type UserPublic, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ToggleUserStatusProps {
  user: UserPublic
  onSuccess: () => void
}

const ToggleUserStatus = ({ user, onSuccess }: ToggleUserStatusProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const isActive = user.is_active !== false
  const nextActive = !isActive

  const mutation = useMutation({
    mutationFn: () =>
      UsersService.setActiveStatus({
        requestBody: { user_ids: [user.id], is_active: nextActive },
      }),
    onSuccess: (result) => {
      setIsOpen(false)
      onSuccess()
      // The endpoint reports per-user outcomes, so a request can succeed at the
      // HTTP level while the action was refused by a safety guard (e.g. the last
      // active superuser). Surface that reason instead of a misleading success.
      if (result.failure_count > 0) {
        showErrorToast(
          result.failed[0]?.reason ?? "The action could not be completed",
        )
      } else {
        showSuccessToast(result.message)
      }
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        {isActive ? <UserX /> : <UserCheck />}
        {isActive ? "Deactivate User" : "Activate User"}
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isActive ? "Deactivate User" : "Activate User"}
          </DialogTitle>
          <DialogDescription>
            {isActive ? (
              <>
                <strong>{user.email}</strong> will no longer be able to sign in
                until the account is reactivated. Are you sure?
              </>
            ) : (
              <>
                <strong>{user.email}</strong> will regain access and be able to
                sign in again. Continue?
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant={isActive ? "destructive" : "default"}
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {isActive ? "Deactivate" : "Activate"}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ToggleUserStatus
