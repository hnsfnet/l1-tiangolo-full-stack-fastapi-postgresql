import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { useState } from "react"

import { type AuditLogPublic, AuditService, UsersService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const ALL = "all"

const ACTION_OPTIONS = [
  { value: "user.create", label: "User created" },
  { value: "user.update", label: "User updated" },
  { value: "user.activate", label: "User activated" },
  { value: "user.deactivate", label: "User deactivated" },
  { value: "user.delete", label: "User deleted" },
  { value: "item.create", label: "Item created" },
  { value: "item.update", label: "Item updated" },
  { value: "item.delete", label: "Item deleted" },
]

const TARGET_TYPE_OPTIONS = [
  { value: "user", label: "User" },
  { value: "item", label: "Item" },
]

function shortId(value: string | null | undefined) {
  if (!value) return "—"
  return value.length > 8 ? `${value.slice(0, 8)}…` : value
}

const columns: ColumnDef<AuditLogPublic>[] = [
  {
    accessorKey: "created_at",
    header: "Time",
    cell: ({ row }) => {
      const value = row.original.created_at
      return (
        <span className="whitespace-nowrap text-sm">
          {value ? new Date(value).toLocaleString() : "—"}
        </span>
      )
    },
  },
  {
    accessorKey: "action",
    header: "Action",
    cell: ({ row }) => <Badge variant="secondary">{row.original.action}</Badge>,
  },
  {
    accessorKey: "target_type",
    header: "Target type",
  },
  {
    accessorKey: "target_id",
    header: "Target",
    cell: ({ row }) => (
      <span className="font-mono text-xs" title={row.original.target_id ?? ""}>
        {shortId(row.original.target_id)}
      </span>
    ),
  },
  {
    accessorKey: "actor_user_id",
    header: "Actor",
    cell: ({ row }) => (
      <span
        className="font-mono text-xs"
        title={row.original.actor_user_id ?? ""}
      >
        {shortId(row.original.actor_user_id)}
      </span>
    ),
  },
  {
    accessorKey: "summary",
    header: "Summary",
  },
]

export const Route = createFileRoute("/_layout/audit")({
  component: Audit,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Audit - FastAPI Template",
      },
    ],
  }),
})

function Audit() {
  const [action, setAction] = useState<string>(ALL)
  const [targetType, setTargetType] = useState<string>(ALL)
  const [actorUserId, setActorUserId] = useState<string>("")

  const { data, isLoading, isError } = useQuery({
    queryKey: ["audit-logs", action, targetType, actorUserId],
    queryFn: () =>
      AuditService.readAuditLogs({
        action: action === ALL ? undefined : action,
        targetType: targetType === ALL ? undefined : targetType,
        actorUserId: actorUserId.trim() ? actorUserId.trim() : undefined,
        skip: 0,
        limit: 100,
      }),
    placeholderData: keepPreviousData,
  })

  const resetFilters = () => {
    setAction(ALL)
    setTargetType(ALL)
    setActorUserId("")
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Audit log</h1>
        <p className="text-muted-foreground">
          Review recent administrative actions
        </p>
      </div>

      <div className="flex flex-col gap-4 rounded-lg border p-4 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="audit-action">Action</Label>
          <Select value={action} onValueChange={setAction}>
            <SelectTrigger id="audit-action" className="w-[200px]">
              <SelectValue placeholder="All actions" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All actions</SelectItem>
              {ACTION_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="audit-target-type">Target type</Label>
          <Select value={targetType} onValueChange={setTargetType}>
            <SelectTrigger id="audit-target-type" className="w-[160px]">
              <SelectValue placeholder="All targets" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All targets</SelectItem>
              {TARGET_TYPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="audit-actor">Actor user ID</Label>
          <Input
            id="audit-actor"
            placeholder="Filter by actor UUID"
            value={actorUserId}
            onChange={(event) => setActorUserId(event.target.value)}
            className="w-[280px]"
          />
        </div>

        <Button variant="outline" onClick={resetFilters}>
          Reset
        </Button>
      </div>

      {isError ? (
        <p className="text-destructive">Failed to load audit logs.</p>
      ) : isLoading ? (
        <p className="text-muted-foreground">Loading audit logs…</p>
      ) : (
        <DataTable columns={columns} data={data?.data ?? []} />
      )}
    </div>
  )
}
