import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { RowSelectionState } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { type ItemsReadItemsData, ItemsService, UsersService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddItem from "@/components/Items/AddItem"
import { columns } from "@/components/Items/columns"
import DeleteItems from "@/components/Items/DeleteItems"
import PendingItems from "@/components/Pending/PendingItems"
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
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/items")({
  component: Items,
  head: () => ({
    meta: [
      {
        title: "Items - FastAPI Template",
      },
    ],
  }),
})

function Items() {
  const { user } = useAuth()
  const isSuperuser = Boolean(user?.is_superuser)

  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [createdFrom, setCreatedFrom] = useState("")
  const [createdTo, setCreatedTo] = useState("")
  const [ownerId, setOwnerId] = useState("all")
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})

  // Debounce the free-text search so we don't refetch on every keystroke.
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timeout)
  }, [search])

  const queryArgs = useMemo<ItemsReadItemsData>(() => {
    const args: ItemsReadItemsData = { skip: 0, limit: 100 }
    const trimmed = debouncedSearch.trim()
    if (trimmed) {
      args.q = trimmed
    }
    if (createdFrom) {
      args.createdFrom = `${createdFrom}T00:00:00`
    }
    if (createdTo) {
      // Include the entire end day.
      args.createdTo = `${createdTo}T23:59:59`
    }
    if (isSuperuser && ownerId !== "all") {
      args.ownerId = ownerId
    }
    return args
  }, [debouncedSearch, createdFrom, createdTo, ownerId, isSuperuser])

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["items", queryArgs],
    queryFn: () => ItemsService.readItems(queryArgs),
    placeholderData: keepPreviousData,
  })

  const { data: usersData } = useQuery({
    queryKey: ["users", "owner-filter"],
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    enabled: isSuperuser,
  })

  // Clear the selection whenever the filters change so we never act on rows
  // that are no longer visible.
  useEffect(() => {
    setRowSelection({})
  }, [queryArgs])

  const items = data?.data ?? []
  const visibleIds = useMemo(
    () => new Set(items.map((item) => item.id)),
    [items],
  )
  const selectedIds = Object.keys(rowSelection).filter(
    (id) => rowSelection[id] && visibleIds.has(id),
  )

  const hasActiveFilters = Boolean(
    debouncedSearch.trim() ||
      createdFrom ||
      createdTo ||
      (isSuperuser && ownerId !== "all"),
  )

  const resetFilters = () => {
    setSearch("")
    setCreatedFrom("")
    setCreatedTo("")
    setOwnerId("all")
  }

  const selectionToolbar =
    selectedIds.length > 0 ? (
      <div className="flex flex-col gap-2 rounded-md border bg-muted/40 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm font-medium">
          {selectedIds.length} selected
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setRowSelection({})}
          >
            Clear selection
          </Button>
          <DeleteItems
            selectedIds={selectedIds}
            onDeleted={() => setRowSelection({})}
          />
        </div>
      </div>
    ) : null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Items</h1>
          <p className="text-muted-foreground">Create and manage your items</p>
        </div>
        <AddItem />
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search title or description"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>

          <div className="flex items-center gap-2">
            <Label
              htmlFor="created-from"
              className="text-sm text-muted-foreground"
            >
              From
            </Label>
            <Input
              id="created-from"
              type="date"
              value={createdFrom}
              max={createdTo || undefined}
              onChange={(e) => setCreatedFrom(e.target.value)}
              className="w-[160px]"
            />
          </div>

          <div className="flex items-center gap-2">
            <Label
              htmlFor="created-to"
              className="text-sm text-muted-foreground"
            >
              To
            </Label>
            <Input
              id="created-to"
              type="date"
              value={createdTo}
              min={createdFrom || undefined}
              onChange={(e) => setCreatedTo(e.target.value)}
              className="w-[160px]"
            />
          </div>

          {isSuperuser && (
            <Select value={ownerId} onValueChange={setOwnerId}>
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="All owners" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All owners</SelectItem>
                {usersData?.data.map((owner) => (
                  <SelectItem key={owner.id} value={owner.id}>
                    {owner.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={resetFilters}>
              Reset filters
            </Button>
          )}
        </div>

        {data && (
          <p className="text-sm text-muted-foreground">
            {data.count} item{data.count === 1 ? "" : "s"} found
            {isFetching && !isLoading ? " · Updating…" : ""}
          </p>
        )}
      </div>

      {isLoading ? (
        <PendingItems />
      ) : items.length === 0 ? (
        hasActiveFilters ? (
          <div className="flex flex-col items-center justify-center text-center py-12">
            <div className="rounded-full bg-muted p-4 mb-4">
              <Search className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold">No items match your filters</h3>
            <p className="text-muted-foreground">
              Try adjusting your search or date range.
            </p>
            <Button variant="outline" className="mt-4" onClick={resetFilters}>
              Reset filters
            </Button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center py-12">
            <div className="rounded-full bg-muted p-4 mb-4">
              <Search className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold">
              You don't have any items yet
            </h3>
            <p className="text-muted-foreground">Add a new item to get started</p>
          </div>
        )
      ) : (
        <DataTable
          columns={columns}
          data={items}
          enableRowSelection
          getRowId={(row) => row.id}
          rowSelection={rowSelection}
          onRowSelectionChange={setRowSelection}
          toolbar={selectionToolbar}
        />
      )}
    </div>
  )
}
